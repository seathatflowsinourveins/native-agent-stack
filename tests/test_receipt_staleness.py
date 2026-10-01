"""scripts/receipt_staleness.py against synthetic host receipts (local fixtures, not host evidence).

The receipts below are written into a temporary tree from a copy of the real receipt schema;
none of them is a recorded observation.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path

from scripts import host_receipts as hr
from scripts import receipt_staleness as rs

REPO_ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-30T00:00:00Z"
NOW_DT = datetime(2026, 10, 30, tzinfo=timezone.utc)

BASE_RECEIPT = {
    "schema_version": 1,
    "id": "",
    "kind": "host_acceptance",
    "host": {"host_id": "", "platform_id": "linux-wsl2-x86_64", "os": "linux", "architecture": "x86_64",
             "second_physical_machine": False},
    "catalog_revision": "0" * 40,
    "component_id": "",
    "stage": "use",
    "commands": [{"cmd": "widget --version", "exit": 0, "duration_s": 0.01, "output_sha256": "0" * 64,
                  "output_excerpt": "widget 1.0.0\n"}],
    "tool_versions": {},
    "observed_at_utc": "",
    "result": "pass",
    "claim": "Synthetic receipt for the staleness report tests.",
    "limitations": ["Synthetic fixture; nothing ran."],
    "evidence_class": "synthetic",
    "reviews": [{"kind": "self", "ref": "tests/test_receipt_staleness.py", "verdict": "agree", "at_utc": ""}],
}


def entry(path, version, observed, shape_ok=True, identity_ok=True, result="pass", host="synthetic-host",
          stage="use"):
    """One per-receipt entry in host_receipts.build_summary()'s shape."""
    return {"path": path, "component_version": version, "observed_at_utc": observed, "shape_ok": shape_ok,
            "platform_identity_ok": identity_ok, "result": result, "stage": stage, "host_id": host}


def summary(**buckets):
    """summary(widget={"linux-wsl2-x86_64": [entries]})."""
    return {"components": {component: {"platforms": {platform: {"receipts": entries}
                                                     for platform, entries in platforms.items()}}
                           for component, platforms in buckets.items()}}


class AssessTests(unittest.TestCase):
    def assess(self, data, pins, max_age_days=30):
        return rs.assess(data, lambda _component: pins, NOW_DT, max_age_days)

    def test_a_stack_alias_is_reported_as_such_and_never_bound(self):
        report = rs.assess(summary(widget={"macos-arm64": [entry("a.json", "1.0.0", "2026-10-20T00:00:00Z")]}),
                           lambda _component: (["1.0.0"], "stack_manifest"), NOW_DT, 30,
                           {"widget": ("widget-winner",)})
        row = report["rows"][0]
        self.assertEqual((row["pin_source"], row["alias_of"], row["current_pins"]),
                         ("stack_alias", ["widget-winner"], []))
        self.assertEqual((row["bound_receipts"], row["flags"], row["pin_moved_hosts"]), (0, ["stack_alias"], []))
        self.assertEqual(row["unbound"][0]["reason"], "stack_alias")
        self.assertEqual((row["grandfathered"], row["info"]), (False, []))
        self.assertEqual((report["status"], report["flag_counts"]["stack_alias"]), ("flagged", 1))

    def test_a_grandfathered_alias_is_informational_and_not_flagged(self):
        data = summary(widget={"macos-arm64": [entry("a.json", "1.0.0", "2026-10-20T00:00:00Z")]})
        report = rs.assess(data, lambda _component: (["1.0.0"], "stack_manifest"), NOW_DT, 30,
                           {"widget": ("widget-winner",)}, {"a.json"})
        row = report["rows"][0]
        self.assertEqual((row["alias_of"], row["grandfathered"], row["info"], row["flags"]),
                         (["widget-winner"], True, ["stack_alias_grandfathered"], []))
        self.assertEqual((row["bound_receipts"], row["unbound"][0]["reason"]), (0, "stack_alias_grandfathered"))
        self.assertEqual((report["status"], report["flagged"]), ("current", 0))
        self.assertEqual(report["info_counts"], {"stack_alias_grandfathered": 1})
        self.assertIn("ok (info: stack_alias_grandfathered)", rs.render_text(report))

    def test_one_non_grandfathered_alias_receipt_keeps_the_row_flagged(self):
        data = summary(widget={"macos-arm64": [entry("a.json", "1.0.0", "2026-10-20T00:00:00Z"),
                                               entry("b.json", "1.0.0", "2026-10-21T00:00:00Z")]})
        report = rs.assess(data, lambda _component: (["1.0.0"], "stack_manifest"), NOW_DT, 30,
                           {"widget": ("widget-winner",)}, {"a.json"})
        row = report["rows"][0]
        self.assertEqual((row["grandfathered"], row["info"], row["flags"]), (False, [], ["stack_alias"]))
        self.assertEqual([item["reason"] for item in row["unbound"]], ["stack_alias_grandfathered", "stack_alias"])
        self.assertEqual(report["status"], "flagged")

    def test_grandfathered_paths_do_not_affect_a_non_alias_row(self):
        report = rs.assess(summary(widget={"linux-wsl2-x86_64": [entry("a.json", "0.9.0", "2026-10-20T00:00:00Z")]}),
                           lambda _component: (["1.0.0"], "landscape_winner"), NOW_DT, 30, {}, {"a.json"})
        row = report["rows"][0]
        self.assertEqual((row["grandfathered"], row["info"], row["flags"]), (False, [], ["no_bound_receipt", "pin_moved"]))

    def test_a_non_alias_row_has_an_empty_alias_list(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a.json", "1.0.0", "2026-10-20T00:00:00Z")]}), (["1.0.0"], "landscape_winner"))
        self.assertEqual(report["rows"][0]["alias_of"], [])

    def test_recent_bound_receipt_is_not_flagged(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a.json", "1.0.0", "2026-10-20T00:00:00Z")]}), (["1.0.0"], "landscape_winner"))
        row = report["rows"][0]
        self.assertEqual(row["flags"], [])
        self.assertEqual(row["latest_bound"]["age_days"], 10)
        self.assertEqual(report["status"], "current")

    def test_old_latest_bound_receipt_is_stale(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a.json", "1.0.0", "2026-09-01T00:00:00Z")]}), (["1.0.0"], "landscape_winner"))
        self.assertEqual(report["rows"][0]["flags"], ["stale"])
        self.assertEqual(report["flag_counts"]["stale"], 1)
        self.assertEqual(report["status"], "flagged")

    def test_window_boundary_is_inclusive(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a.json", "1.0.0", "2026-09-30T00:00:00Z")]}), (["1.0.0"], "landscape_winner"))
        self.assertEqual(report["rows"][0]["latest_bound"]["age_days"], 30)
        self.assertEqual(report["rows"][0]["flags"], [])

    def test_a_newer_bound_receipt_clears_an_older_one(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("old.json", "1.0.0", "2026-08-01T00:00:00Z"),
            entry("new.json", "1.0.0", "2026-10-25T00:00:00Z")]}), (["1.0.0"], "landscape_winner"))
        row = report["rows"][0]
        self.assertEqual((row["latest_bound"]["path"], row["latest_bound"]["age_days"]), ("new.json", 5))
        self.assertEqual((row["bound_receipts"], row["flags"]), (2, []))

    def test_latest_bound_is_the_newest_bound_one_not_the_newest_overall(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("old-pin.json", "0.9.0", "2026-10-29T00:00:00Z"),
            entry("bound.json", "1.0.0", "2026-10-01T00:00:00Z")]}), (["1.0.0"], "landscape_winner"))
        row = report["rows"][0]
        self.assertEqual(row["latest_bound"]["path"], "bound.json")
        self.assertEqual(row["flags"], ["pin_moved"])
        self.assertEqual(row["unbound"], [{"path": "old-pin.json", "component_version": "0.9.0",
                                           "observed_at_utc": "2026-10-29T00:00:00Z", "reason": "pin_moved"}])

    def test_re_recording_at_the_new_pin_clears_pin_moved(self):
        # The old receipt stays in the tree (update.md: receipts are not edited or deleted);
        # once the same host has a newer receipt at the current pin the bucket is done.
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("old-pin.json", "0.9.0", "2026-10-01T00:00:00Z"),
            entry("re-recorded.json", "1.0.0", "2026-10-28T00:00:00Z")]}), (["1.0.0"], "landscape_winner"))
        row = report["rows"][0]
        self.assertEqual((row["flags"], row["pin_moved_hosts"]), ([], []))
        self.assertEqual([item["path"] for item in row["unbound"]], ["old-pin.json"])
        self.assertEqual(report["status"], "current")

    def test_pin_moved_names_each_host_and_stage_still_at_the_old_pin(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a-old.json", "0.9.0", "2026-10-01T00:00:00Z", host="host-a"),
            entry("a-new.json", "1.0.0", "2026-10-28T00:00:00Z", host="host-a"),
            entry("b-old.json", "0.9.0", "2026-10-02T00:00:00Z", host="host-b"),
            entry("a-verify.json", "0.9.0", "2026-10-03T00:00:00Z", host="host-a", stage="verify")]}),
            (["1.0.0"], "landscape_winner"))
        row = report["rows"][0]
        self.assertEqual(row["flags"], ["pin_moved"])
        self.assertEqual(row["pin_moved_hosts"], ["host-a/verify", "host-b/use"])

    def test_invalid_receipts_neither_raise_nor_clear_pin_moved(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("old-pin.json", "0.9.0", "2026-10-01T00:00:00Z"),
            entry("bad-new.json", "1.0.0", "2026-10-28T00:00:00Z", shape_ok=False)]}),
            (["1.0.0"], "landscape_winner"))
        self.assertEqual(report["rows"][0]["flags"], ["no_bound_receipt", "pin_moved"])

    def test_only_old_pin_receipts_means_no_bound_receipt_and_pin_moved(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a.json", "0.9.0", "2026-10-29T00:00:00Z")]}), (["1.0.0"], "landscape_winner"))
        row = report["rows"][0]
        self.assertIsNone(row["latest_bound"])
        self.assertEqual(row["flags"], ["no_bound_receipt", "pin_moved"])

    def test_schema_invalid_or_wrong_platform_receipts_do_not_bind_and_are_not_pin_moves(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("bad.json", "1.0.0", "2026-10-29T00:00:00Z", shape_ok=False),
            entry("mac.json", "1.0.0", "2026-10-29T00:00:00Z", identity_ok=False)]}),
            (["1.0.0"], "landscape_winner"))
        row = report["rows"][0]
        self.assertEqual(row["flags"], ["no_bound_receipt"])
        self.assertEqual(sorted(item["reason"] for item in row["unbound"]),
                         ["platform_identity_mismatch", "schema_invalid"])

    def test_no_current_pin_is_reported_instead_of_judged(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a.json", "1.0.0", "2026-01-01T00:00:00Z")]}), ([], "none"))
        self.assertEqual(report["rows"][0]["flags"], ["no_current_pin"])

    def test_pins_bind_through_host_receipts_normalization(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a.json", "v1.0.0", "2026-10-29T00:00:00Z")]}), (["1.0.0"], "landscape_winner"))
        self.assertEqual(report["rows"][0]["bound_receipts"], 1)

    def test_any_of_several_winner_pins_binds(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a.json", "2.0.0", "2026-10-29T00:00:00Z")]}), (["1.0.0", "2.0.0"], "landscape_winner"))
        self.assertEqual(report["rows"][0]["flags"], [])

    def test_rows_are_per_platform_and_component_in_order(self):
        report = self.assess(summary(
            zeta={"macos-arm64": [entry("z.json", "1.0.0", "2026-10-29T00:00:00Z")]},
            alpha={"macos-arm64": [entry("a.json", "1.0.0", "2026-10-29T00:00:00Z")],
                   "linux-wsl2-x86_64": [entry("b.json", "1.0.0", "2026-10-29T00:00:00Z")]}),
            (["1.0.0"], "stack_manifest"))
        self.assertEqual([(row["platform_id"], row["component_id"]) for row in report["rows"]],
                         [("linux-wsl2-x86_64", "alpha"), ("macos-arm64", "alpha"), ("macos-arm64", "zeta")])

    def test_custom_window(self):
        report = self.assess(summary(widget={"linux-wsl2-x86_64": [
            entry("a.json", "1.0.0", "2026-10-20T00:00:00Z")]}), (["1.0.0"], "landscape_winner"), max_age_days=7)
        self.assertEqual(report["rows"][0]["flags"], ["stale"])


class SyntheticTreeTests(unittest.TestCase):
    """End to end through host_receipts.build_summary() on a temporary tree."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "adoption").mkdir()
        (self.root / "manifests").mkdir()
        (self.root / "catalogs" / "landscape").mkdir(parents=True)
        (self.root / "adoption" / "host-receipt.schema.json").write_bytes(
            (REPO_ROOT / "adoption" / "host-receipt.schema.json").read_bytes())
        (self.root / "adoption" / "manifest.json").write_text(json.dumps({"platform_profiles": [
            {"id": "linux-wsl2-x86_64", "os": "linux", "architecture": "x86_64"},
            {"id": "macos-arm64", "os": "macos", "architecture": "arm64"}]}), encoding="utf-8")
        (self.root / "manifests" / "stack.json").write_text(json.dumps({"components": [
            {"id": "widget", "version": "1.0.0"}, {"id": "gadget", "version": "3.1.0"}]}), encoding="utf-8")
        (self.root / "catalogs" / "landscape" / "foundation.json").write_text(json.dumps({"layers": [
            {"winners": [{"component_id": "widget", "pin": "2.0.0"}]}]}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def write_receipt(self, component, version, observed, platform="linux-wsl2-x86_64", host="synthetic-host-20260901"):
        receipt = copy.deepcopy(BASE_RECEIPT)
        date = observed[:10].replace("-", "")
        receipt["id"] = f"{host}--{component}--use--{date}"
        receipt["host"]["host_id"] = host
        receipt["host"]["platform_id"] = platform
        if platform == "macos-arm64":
            receipt["host"].update(os="macos", architecture="arm64")
        receipt["component_id"] = component
        receipt["tool_versions"] = {component: version}
        receipt["observed_at_utc"] = observed
        receipt["reviews"][0]["at_utc"] = observed
        directory = self.root / "evidence" / "hosts" / host
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{receipt['id']}.json"
        path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        errors: list[str] = []
        hr.validate_receipt_shape(self.root, receipt, path.name, errors)
        self.assertEqual(errors, [], "synthetic receipt must be schema-valid to exercise binding")
        return path

    def run_report(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = rs.main(["--root", str(self.root), "--json", "--now", NOW, *extra])
        return code, json.loads(out.getvalue())

    def test_winner_pin_bump_retires_the_old_receipt_and_stack_fallback_binds(self):
        self.write_receipt("widget", "1.0.0", "2026-10-25T00:00:00Z")          # before the winner pin moved to 2.0.0
        self.write_receipt("gadget", "3.1.0", "2026-08-01T00:00:00Z")          # no winner; stack pin; 90 days old
        self.write_receipt("gadget", "3.1.0", "2026-10-29T00:00:00Z", platform="macos-arm64",
                           host="synthetic-mac-20261029")
        code, report = self.run_report()
        self.assertEqual(code, 0)
        rows = {(row["platform_id"], row["component_id"]): row for row in report["rows"]}
        widget = rows[("linux-wsl2-x86_64", "widget")]
        self.assertEqual((widget["current_pins"], widget["pin_source"]), (["2.0.0"], "landscape_winner"))
        self.assertEqual(widget["flags"], ["no_bound_receipt", "pin_moved"])
        gadget_linux = rows[("linux-wsl2-x86_64", "gadget")]
        self.assertEqual((gadget_linux["pin_source"], gadget_linux["flags"]), ("stack_manifest", ["stale"]))
        self.assertEqual(gadget_linux["latest_bound"]["age_days"], 90)
        self.assertEqual(rows[("macos-arm64", "gadget")]["flags"], [])
        self.assertEqual(report["flagged"], 2)

    def test_re_recording_after_the_pin_bump_clears_the_bucket_end_to_end(self):
        self.write_receipt("widget", "1.0.0", "2026-10-01T00:00:00Z")          # before the pin moved
        self.write_receipt("widget", "2.0.0", "2026-10-28T00:00:00Z")          # same host, new pin
        code, report = self.run_report()
        self.assertEqual(code, 0)
        row = report["rows"][0]
        self.assertEqual((row["flags"], row["bound_receipts"], len(row["unbound"])), ([], 1, 1))
        self.assertEqual(report["status"], "current")

    def test_out_writes_outside_the_checkout_and_is_refused_inside_it(self):
        self.write_receipt("gadget", "3.1.0", "2026-10-29T00:00:00Z")
        with tempfile.TemporaryDirectory() as elsewhere:
            target = Path(elsewhere) / "report" / "staleness.json"
            code, report = self.run_report("--out", str(target))
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), report)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as refused:
            rs.main(["--root", str(self.root), "--out", str(self.root / "report.json")])
        self.assertEqual(refused.exception.code, 2)
        self.assertFalse((self.root / "report.json").exists())

    def test_empty_tree_reports_current(self):
        code, report = self.run_report()
        self.assertEqual((code, report["rows"], report["status"]), (0, [], "current"))

    def test_text_report_names_each_bucket(self):
        self.write_receipt("gadget", "3.1.0", "2026-08-01T00:00:00Z")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(rs.main(["--root", str(self.root), "--now", NOW]), 0)
        self.assertIn("linux-wsl2-x86_64  gadget: latest bound 2026-08-01T00:00:00Z (90 days", out.getvalue())
        self.assertIn("; stale", out.getvalue())

    def test_stack_alias_of_a_winner_never_binds_end_to_end(self):
        # 'gadget-alias' shares its repository with the differently named winner 'gadget-winner'; its
        # receipt at the stack version must not be reported as bound (platform_status never joins it).
        (self.root / "manifests" / "stack.json").write_text(json.dumps({"components": [
            {"id": "gadget-alias", "version": "3.1.0", "repository": "https://github.com/example/gadget"}]}),
            encoding="utf-8")
        (self.root / "catalogs" / "landscape" / "foundation.json").write_text(json.dumps({"layers": [
            {"winners": [{"component_id": "gadget-winner", "pin": "3.1.0",
                          "repository": "https://github.com/example/gadget/releases/tag/v3.1.0"}]}]}),
            encoding="utf-8")
        path = self.write_receipt("gadget-alias", "3.1.0", "2026-10-29T00:00:00Z")
        code, report = self.run_report()
        self.assertEqual(code, 0)
        row = report["rows"][0]
        self.assertEqual((row["component_id"], row["alias_of"], row["pin_source"], row["current_pins"]),
                         ("gadget-alias", ["gadget-winner"], "stack_alias", []))
        self.assertEqual((row["bound_receipts"], row["latest_bound"], row["flags"]), (0, None, ["stack_alias"]))
        self.assertEqual(row["unbound"][0]["reason"], "stack_alias")
        self.assertEqual(row["unbound"][0]["path"], path.relative_to(self.root).as_posix())
        self.assertEqual(report["flag_counts"]["stack_alias"], 1)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(rs.main(["--root", str(self.root), "--now", NOW]), 0)
        self.assertIn("alias of winner gadget-winner, never bound; 0/1 bound; stack_alias", out.getvalue())

        # Grandfathering that exact recorded claim (path and claim_sha256) turns the row informational end
        # to end; an altered claim loses the exemption and the flag returns.
        relative = path.relative_to(self.root).as_posix()
        entry = {"canonical_component_id": "gadget-winner", "date": "2026-10-29", "reason": "test",
                 "claim_sha256": hr.receipt_claim_sha256(json.loads(path.read_text(encoding="utf-8")))}
        with mock.patch.object(hr, "GRANDFATHERED_ALIAS_RECEIPTS", {relative: entry}):
            code, report = self.run_report()
            row = report["rows"][0]
            self.assertEqual((code, row["flags"], row["info"], row["grandfathered"]),
                             (0, [], ["stack_alias_grandfathered"], True))
            self.assertEqual((report["status"], report["flag_counts"]["stack_alias"]), ("current", 0))
            altered = json.loads(path.read_text(encoding="utf-8"))
            altered["claim"] = f"{altered.get('claim', '')} (edited after recording)"
            path.write_text(json.dumps(altered, indent=2) + "\n", encoding="utf-8")
            code, report = self.run_report()
            self.assertEqual((report["rows"][0]["flags"], report["status"]), (["stack_alias"], "flagged"))

    def test_bad_now_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as bad:
            rs.main(["--root", str(self.root), "--now", "yesterday"])
        self.assertEqual(bad.exception.code, 2)


class RepositoryRunTests(unittest.TestCase):
    def test_runs_on_this_checkout_and_writes_nothing(self):
        before = sorted(p.relative_to(REPO_ROOT).as_posix() for p in (REPO_ROOT / "evidence" / "hosts").rglob("*")) \
            if (REPO_ROOT / "evidence" / "hosts").is_dir() else []
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(rs.main(["--json"]), 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report["max_age_days"], rs.DEFAULT_MAX_AGE_DAYS)
        after = sorted(p.relative_to(REPO_ROOT).as_posix() for p in (REPO_ROOT / "evidence" / "hosts").rglob("*")) \
            if (REPO_ROOT / "evidence" / "hosts").is_dir() else []
        self.assertEqual(before, after)

    def test_real_grandfathered_alias_receipts_are_informational_not_flagged(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(rs.main(["--json"]), 0)
        report = json.loads(out.getvalue())
        alias_paths = {item["path"] for row in report["rows"] if row["alias_of"] for item in row["unbound"]}
        self.assertEqual(alias_paths, set(hr.GRANDFATHERED_ALIAS_RECEIPTS))
        self.assertEqual(report["flag_counts"]["stack_alias"], 0)
        self.assertEqual(report["info_counts"]["stack_alias_grandfathered"], len(hr.GRANDFATHERED_ALIAS_RECEIPTS))
        for row in report["rows"]:
            if row["alias_of"]:
                self.assertEqual((row["grandfathered"], row["flags"]), (True, []))


class ReceiptReadingWorkflowsCheckOutFullHistory(unittest.TestCase):
    """host_receipts validates each receipt's catalog_revision with `git cat-file -e`, which a
    shallow clone never contains, so every workflow that reads receipts must fetch full history."""

    def test_receipt_readers_set_fetch_depth_zero(self):
        workflows = Path(__file__).resolve().parents[1] / ".github/workflows"
        readers = [path for path in sorted(workflows.glob("*.yml"))
                   if "receipt_staleness.py" in path.read_text(encoding="utf-8")]
        self.assertTrue(readers)
        for path in readers:
            self.assertIn("fetch-depth: 0", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
