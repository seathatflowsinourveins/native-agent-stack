"""Synthetic integration tests: metadata proposals are not model acceptance."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import freshness_propose as fp


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-07T01:00:00Z"
SHA = "a" * 40
NEW_SHA = "b" * 40
POLICY = {"max_release_age_days": 42, "max_landscape_age_days": 7, "refresh_lead_days": 2}


def inventory():
    return {"schema_version": 1, "inventory_status": "complete", "policy": POLICY,
            "packages": [], "models": [{
                "id": "embedding", "role": "embedding", "consumer": "memory", "model_id": "vendor/embed",
                "revision": SHA, "release_date": "2026-09-01", "release_source": "https://huggingface.co/vendor/embed",
                "checked_at": "2026-10-06", "status": "in_use",
                "release_line": {"kind": "huggingface", "repository": "vendor/embed", "ref": "main"}}]}


def observed(value=SHA, *, kind="repository_revision", release_date=None):
    return {"status": "observed", "value": value, "source": "https://huggingface.co/vendor/embed",
            "release_date": release_date, "evidence_kind": kind, "exit_code": 0}


class CollectModelCurrencyTests(unittest.TestCase):
    def setUp(self):
        # Shape validation has its own tests in scripts.validate; the collector
        # must still invoke it before source reads, with age enforcement off.
        self.schema = patch.object(fp, "_model_currency_problems", return_value=[])
        self.check_schema = self.schema.start()
        self.addCleanup(self.schema.stop)
        (ROOT / ".runtime").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="model-currency-", dir=ROOT / ".runtime")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "inventory.json"

    def collect(self, document, reader=None):
        self.path.write_text(json.dumps(document), encoding="utf-8")
        before = self.path.read_bytes()
        result = fp.collect_model_currency(ROOT, self.path, checked_at_utc=NOW,
                                           reader=reader or (lambda line: observed()))
        self.assertEqual(self.path.read_bytes(), before)
        return result

    def test_revision_candidate_never_resets_release_date_or_claims_new_weights(self):
        result = self.collect(inventory(), lambda line: {
            **observed(NEW_SHA), "repository_last_modified": NOW, "repository_created_at": NOW})
        self.assertEqual(result["observations"][0]["recorded_release_date"], "2026-09-01")
        self.assertIsNone(result["observations"][0]["release_date"])
        self.assertEqual(result["proposals"][0]["action"], "review_revision_candidate")
        self.assertIn("no acceptance", result["scope"])

    def test_unchanged_line_does_not_require_review(self):
        result = self.collect(inventory())
        self.assertFalse(result["review_required"])
        self.assertEqual(result["coverage"], {"packages": 0, "models": 1, "unknown": 0})

    def test_unknown_source_never_counts_as_current(self):
        result = self.collect(inventory(), lambda line: {"status": "unknown", "reason": "source unavailable", "exit_code": 7})
        self.assertEqual(result["coverage"]["unknown"], 1)
        self.assertEqual(result["observations"][0]["exit_code"], 7)
        self.assertEqual(result["proposals"][0]["action"], "source_review")

    def test_newer_package_and_republished_lower_version_are_distinct(self):
        doc = inventory()
        doc["packages"] = [{"id": "runtime", "latest_version": "2.0.0", "release_date": "2026-09-30",
                            "release_source": "https://pypi.org/project/runtime/2.0.0/", "checked_at": "2026-10-06",
                            "release_line": {"kind": "pypi", "package": "runtime"}}]
        for candidate, newer in (("2.0.1", True), ("1.9.9", False)):
            with self.subTest(candidate=candidate):
                result = self.collect(doc, lambda line: observed(candidate, kind="published_release", release_date="2026-10-07")
                                      if line["kind"] == "pypi" else observed())
                self.assertEqual(result["observations"][0]["newer"], newer)
                self.assertEqual(result["proposals"][0]["action"], "review_newer_release" if newer else "review_release_difference")

    def test_landscape_refresh_starts_day_five_and_expires_after_day_seven(self):
        for check_date, due, expired in (("2026-10-03", False, False), ("2026-10-02", True, False),
                                         ("2026-09-30", True, False), ("2026-09-29", True, True)):
            with self.subTest(check_date=check_date):
                doc = inventory()
                doc["models"][0]["release_date"] = "2026-08-01"
                doc["models"][0]["landscape_check"] = {"date": check_date, "sources": ["https://example.org/source"],
                                                        "newer_candidates": [], "reason": "reviewed alternatives"}
                result = self.collect(doc)
                self.assertEqual(result["landscape"][0]["refresh_due"], due)
                self.assertEqual(result["landscape"][0]["expired"], expired)

    def test_package_bound_uses_package_age_and_retains_old_weight_identity(self):
        doc = inventory()
        doc["packages"] = [{"id": "runtime", "latest_version": "2.0.0", "release_date": "2026-10-01",
                            "release_source": "https://pypi.org/project/runtime/2.0.0/", "checked_at": "2026-10-06",
                            "release_line": {"kind": "pypi", "package": "runtime"}}]
        row = doc["models"][0]
        row.update(status="package_bound", release_date="2025-01-01", package={"id": "runtime", "version": "2.0.0"})
        del row["release_line"]
        result = self.collect(doc, lambda line: observed("2.0.1", kind="published_release", release_date="2026-10-07"))
        self.assertEqual(result["landscape"][0]["release_age_days"], 6)
        self.assertFalse(result["landscape"][0]["refresh_due"])
        self.assertEqual(result["observations"][1]["recorded_release_date"], "2025-01-01")
        self.assertEqual(result["observations"][1]["revision"], SHA)
        self.assertEqual(result["proposals"][1]["package"]["version"], "2.0.0")
        doc["packages"][0]["release_date"] = "2026-01-01"
        result = self.collect(doc, lambda line: observed("2.0.0", kind="published_release", release_date="2026-01-01"))
        self.assertTrue(result["landscape"][0]["refresh_due"])
        self.assertTrue(result["landscape"][0]["expired"])

    def test_landscape_refresh_precedes_the_42_day_transition(self):
        doc = inventory()
        doc["models"][0]["release_date"] = "2026-08-26"  # Exactly 42 days old.
        doc["models"][0]["landscape_check"] = {"date": "2026-09-30", "sources": ["https://example.org/source"],
                                                "newer_candidates": [], "reason": "reviewed alternatives"}
        result = self.collect(doc)
        self.assertTrue(result["landscape"][0]["refresh_due"])
        self.assertFalse(result["landscape"][0]["expired"])
        self.assertEqual(result["proposals"][0]["action"], "refresh_landscape")

    def test_pending_empty_inventory_is_reported_without_any_source_call(self):
        doc = {"schema_version": 1, "inventory_status": "pending", "policy": POLICY, "packages": [], "models": []}
        reader = Mock(side_effect=AssertionError("pending inventory must not fetch"))
        result = self.collect(doc, reader)
        self.assertEqual(result["proposals"][0]["action"], "complete_inventory")
        reader.assert_not_called()

    def test_package_bound_always_follows_its_package_line(self):
        doc = inventory()
        doc["packages"] = [{"id": "runtime", "latest_version": "2.0.0", "release_date": "2026-10-01",
                            "release_source": "https://pypi.org/project/runtime/2.0.0/", "checked_at": "2026-10-06",
                            "release_line": {"kind": "pypi", "package": "runtime"}}]
        # The retained model line describes weights; the shipping-package
        # contract must win for both the primary check and the effective age.
        doc["models"][0].update(status="package_bound", package={"id": "runtime", "version": "2.0.0"})
        reader = Mock(return_value=observed("2.0.0", kind="published_release", release_date="2026-10-01"))
        result = self.collect(doc, reader)
        self.assertTrue(all(call.args[0]["kind"] == "pypi" for call in reader.call_args_list))
        self.assertEqual(result["observations"][1]["current"], "2.0.0")
        self.assertFalse(result["review_required"])

    def test_nonbinding_package_metadata_cannot_crash_primary_checks(self):
        doc = inventory()
        doc["models"][0]["package"] = {"id": "not-a-binding", "version": "x"}
        result = self.collect(doc)
        self.assertEqual(result["observations"][0]["current"], SHA)
        self.assertNotIn("package", result["observations"][0])

    def test_invalid_inventory_is_rejected_before_any_source_or_write(self):
        self.check_schema.return_value = ["invalid row"]
        self.path.write_text(json.dumps(inventory()), encoding="utf-8")
        with self.assertRaisesRegex(fp.FreshnessProposeError, "invalid row"):
            fp.collect_model_currency(ROOT, self.path, checked_at_utc=NOW, reader=Mock(side_effect=AssertionError))

    def test_offline_dry_run_never_starts_a_child_or_writes_state(self):
        self.path.write_text(json.dumps(inventory()), encoding="utf-8")
        state = Path(self.temp.name) / "never-created"
        stdout = io.StringIO()
        with patch.object(fp, "_model_run_json", side_effect=AssertionError), contextlib.redirect_stdout(stdout):
            self.assertEqual(fp.main(["--model-currency", "--model-inventory", str(self.path), "--offline", "--dry-run",
                                      "--state-dir", str(state), "--checked-at-utc", NOW]), 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["coverage"]["unknown"], 1)
        self.assertEqual(result["proposal_paths"], [])
        self.assertFalse(state.exists())


class ModelReleaseReaderTests(unittest.TestCase):
    def test_hf_command_disables_implicit_credentials_and_retains_metadata_only(self):
        run = Mock(return_value={"sha": NEW_SHA, "created_at": NOW, "last_modified": NOW})
        line = {"kind": "huggingface", "repository": "vendor/embed", "ref": "main"}
        reader = fp.ModelReleaseReader(run_json=run)
        value = reader(line)
        self.assertIsNone(value["release_date"])
        self.assertEqual(value["value"], NEW_SHA)
        argv = run.call_args.args[0]
        self.assertIn("HF_HUB_DISABLE_IMPLICIT_TOKEN=1", argv)
        self.assertEqual(argv[4:], ["models", "info", "vendor/embed", "--revision", "main", "--expand",
                                  "sha,createdAt,lastModified", "--format", "json"])
        self.assertEqual(reader(line), value)
        self.assertEqual(run.call_count, 1)

    def test_github_budget_below_500_prevents_release_call(self):
        run = Mock(return_value={"resources": {"core": {"remaining": 499}}})
        value = fp.ModelReleaseReader(run_json=run)({"kind": "github_release", "repository": "vendor/runtime"})
        self.assertEqual(value["status"], "unknown")
        self.assertIn("below 500", value["reason"])
        run.assert_called_once_with(["gh", "api", "rate_limit"])

    def test_github_check_is_cached_and_decrements_its_conservative_budget(self):
        run = Mock(side_effect=[{"resources": {"core": {"remaining": 500}}},
                                {"tag_name": "v2.0.1", "published_at": NOW, "prerelease": False, "draft": False}])
        reader = fp.ModelReleaseReader(run_json=run)
        line = {"kind": "github_release", "repository": "vendor/runtime"}
        self.assertEqual(reader(line)["value"], "v2.0.1")
        self.assertEqual(reader({**line, "repository": "vendor/other"})["status"], "unknown")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0], ["gh", "api", "--cache", "120s", "repos/vendor/runtime/releases/latest"])

    def test_pypi_yanked_only_release_stays_unknown(self):
        fetch = Mock(return_value={"info": {"version": "2.0.1"}, "urls": [{"yanked": True, "upload_time_iso_8601": NOW}]})
        value = fp.ModelReleaseReader(pypi_json=fetch)({"kind": "pypi", "package": "runtime"})
        self.assertEqual(value["status"], "unknown")

    def test_malformed_primary_metadata_and_vendor_page_stay_unknown(self):
        reader = fp.ModelReleaseReader(run_json=lambda argv: {"sha": "main"})
        self.assertEqual(reader({"kind": "huggingface", "repository": "vendor/embed", "ref": "main"})["status"], "unknown")
        self.assertEqual(reader({"kind": "vendor_page", "url": "https://example.org/releases"})["status"], "unknown")

    def test_native_command_closes_stdin_and_keeps_failure_exit_without_raw_diagnostics(self):
        result = Mock(returncode=69, stdout="", stderr="private diagnostic must not be retained")
        with patch.object(fp.subprocess, "run", return_value=result) as run:
            with self.assertRaises(fp.ModelSourceError) as error:
                fp._model_run_json(["hf", "models", "info", "vendor/embed"])
        self.assertEqual(error.exception.exit_code, 69)
        self.assertNotIn("private", str(error.exception))
        self.assertEqual(run.call_args.kwargs["stdin"], fp.subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["timeout"], 30)


class ModelCurrencyPrivateOutputTests(unittest.TestCase):
    def test_private_dated_proposals_are_append_only_and_mode_0600(self):
        with tempfile.TemporaryDirectory(prefix="model-currency-state-", dir=Path.home() / ".cache") as directory:
            root = Path(directory) / "checkout"
            state = Path(directory) / "state"
            report = {"generated_at": NOW, "review_required": True, "scope": "review only",
                      "proposals": [{"action": "source_review", "id": "embedding"}]}
            paths = fp.write_model_currency_review(root, state, report)
            original = Path(paths[0]).read_bytes()
            another = fp.write_model_currency_review(root, state, report)
            self.assertTrue(set(paths).isdisjoint(another))
            self.assertEqual(Path(paths[0]).read_bytes(), original)
            self.assertTrue(all(Path(p).stat().st_mode & 0o777 == 0o600 for p in paths + another))
            self.assertEqual(state.stat().st_mode & 0o777, 0o700)

    def test_checkout_and_other_git_checkout_outputs_are_refused(self):
        report = {"review_required": True}
        with self.assertRaises(fp.FreshnessProposeError):
            fp.write_model_currency_review(ROOT, ROOT / ".cache/state", report)
        with tempfile.TemporaryDirectory(prefix="model-currency-git-", dir=Path.home() / ".cache") as directory:
            path = Path(directory)
            (path / ".git").touch()
            with self.assertRaises(fp.FreshnessProposeError):
                fp.write_model_currency_review(ROOT, path / "state", report)

    def test_legacy_mode_rejects_model_flags_and_preserves_apply_arguments(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            fp.main(["--artifact-dir", "/artifact", "--run-url", "https://example.org/run", "--offline"])
        stdout = io.StringIO()
        with patch.object(fp, "apply", return_value={"legacy": True}) as apply, contextlib.redirect_stdout(stdout):
            self.assertEqual(fp.main(["--artifact-dir", "/artifact", "--run-url", "https://example.org/run"]), 0)
        apply.assert_called_once_with(ROOT, Path("/artifact"), "https://example.org/run", None)
        self.assertEqual(json.loads(stdout.getvalue()), {"legacy": True})

    def test_daily_timer_uses_proposal_preflight_and_keeps_existing_due_file_command(self):
        service = (ROOT / "adoption/templates/systemd/stack-currency.service").read_text()
        self.assertIn("ExecStartPre=-/usr/bin/python3 @REPOSITORY@/scripts/freshness_propose.py --model-currency", service)
        self.assertIn("ExecStart=/usr/bin/python3 @REPOSITORY@/scripts/currency_due.py", service)
        self.assertIn("Nice=19", service)
        self.assertIn("IOSchedulingClass=idle", service)
        self.assertNotIn("install.sh", service)


class ModelCurrencyValidatorIntegrationTests(unittest.TestCase):
    def test_age_expiry_is_reported_using_the_shared_schema_without_enforcing_age(self):
        from scripts import validate
        if not hasattr(validate, "model_currency_problems"):
            self.skipTest("validator companion change not yet integrated")
        doc = inventory()
        doc["models"][0]["release_date"] = "2026-01-01"
        doc["models"][0]["landscape_check"] = {
            "date": "2026-09-01", "sources": ["https://huggingface.co/vendor/embed"],
            "newer_candidates": [], "reason": "dated source review"}
        doc["models"][0]["overturn"] = "A newer model wins the consuming client's native evaluation."
        with patch.object(validate, "model_currency_problems", wraps=validate.model_currency_problems) as check:
            self.assertEqual(fp._model_currency_problems(doc, fp.date(2026, 10, 7)), [])
        self.assertFalse(check.call_args.kwargs["enforce_age"])
        self.assertTrue(validate.model_currency_problems(doc, today=fp.date(2026, 10, 7)))


if __name__ == "__main__":
    (ROOT / ".cache").mkdir(exist_ok=True)
    unittest.main()
