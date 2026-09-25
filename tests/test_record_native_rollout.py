"""Tests for tools/sota-convergence/record_native_rollout.py and its sibling schema
tools/sota-convergence/native-rollout-receipt.schema.json.

Every receipt and landscape document here is a synthetic fixture; nothing reads or
writes the repository's real catalogs/landscape/*.json files.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"
TOOL_PATH = TOOL_DIR / "record_native_rollout.py"
SCHEMA_PATH = TOOL_DIR / "native-rollout-receipt.schema.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.platform_status import StatusContext  # noqa: E402


def load_module(name, filename):
    path = TOOL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


record_native_rollout = load_module("record_native_rollout", "record_native_rollout.py")


def valid_command(**overrides):
    command = {
        "argv": ["qmd", "search", "example"], "cwd": "${STACK_HOME}", "env_names": [],
        "started_utc": "2026-09-25T00:00:00Z", "elapsed_s": 0.5, "exit": 0,
        "stdout_sha256": "0" * 64, "stderr_sha256": "1" * 64, "assertion": "exit 0 and results found",
    }
    command.update(overrides)
    return command


def valid_tier(tier, result="passed", commands=None, unavailable_reason=None):
    doc = {"tier": tier, "commands": commands if commands is not None else ([valid_command()] if result == "passed" else [])}
    doc["result"] = result
    if unavailable_reason is not None:
        doc["unavailable_reason"] = unavailable_reason
    return doc


def valid_receipt(*, component_id="qmd", version="2.8.4", host_id="wsl-test-host-20260925",
                  status="passed", tiers=None, evidence_class_claimed="native_proven"):
    return {
        "schema_version": 1, "id": f"{component_id}--{version}--r1", "kind": "native_rollout", "status": status,
        "identity": {"component_id": component_id, "version": version, "host_id": host_id},
        "upstream": {"repo": "https://github.com/example/qmd", "tag": f"v{version}",
                    "artifact_url": "https://registry.npmjs.org/example/-/qmd.tgz", "sha256": "a" * 64},
        "install": {"class": "npm", "root": "${STACK_HOME}/tools/qmd-" + version,
                   "marker_sha256": "b" * 64, "argv": ["npm", "install"], "private_env_names": []},
        "tiers": tiers if tiers is not None else [
            valid_tier("T0"), valid_tier("T1", "unavailable", unavailable_reason="no GPU on this host"),
            valid_tier("T2"), valid_tier("T4"), valid_tier("T5"),
        ],
        "independent": {"rerun_label": "second session, same host", "agreement": "same_result", "loki": []},
        "decision": "retain", "evidence_class_claimed": evidence_class_claimed,
        "limitations": ["Synthetic fixture; not a real rollout."],
        "retained_native_failures": [],
    }


class SchemaFileTests(unittest.TestCase):
    def test_schema_is_valid_json_and_names_every_tier(self):
        document = json.loads(SCHEMA_PATH.read_text())
        self.assertEqual(document["properties"]["tiers"]["items"]["properties"]["tier"]["enum"], list(record_native_rollout.TIERS))


class ValidateReceiptTests(unittest.TestCase):
    def test_valid_receipt_has_no_errors(self):
        self.assertEqual(record_native_rollout.validate_receipt(valid_receipt()), [])

    def test_not_a_dict(self):
        self.assertTrue(record_native_rollout.validate_receipt(["not", "a", "dict"]))

    def test_missing_top_level_fields(self):
        errors = record_native_rollout.validate_receipt({"schema_version": 1})
        self.assertTrue(any("kind" in e for e in errors))
        self.assertTrue(any("status" in e for e in errors))
        self.assertTrue(any("identity" in e for e in errors))

    def test_upstream_needs_tag_or_commit(self):
        receipt = valid_receipt()
        del receipt["upstream"]["tag"]
        errors = record_native_rollout.validate_receipt(receipt)
        self.assertTrue(any("tag or commit" in e for e in errors))

    def test_upstream_commit_must_be_full_sha(self):
        receipt = valid_receipt()
        del receipt["upstream"]["tag"]
        receipt["upstream"]["commit"] = "not-a-sha"
        errors = record_native_rollout.validate_receipt(receipt)
        self.assertTrue(any("commit" in e for e in errors))

    def test_install_root_needs_the_stack_home_placeholder(self):
        receipt = valid_receipt()
        # A real host path with no ${STACK_HOME} placeholder must be refused; this literal
        # avoids scripts/validate.py's personal-home-path scan pattern on purpose (it is not
        # meant to look like a real path, only to lack the placeholder).
        receipt["install"]["root"] = "/opt/codex-ecosystem-fixture/tools/qmd-2.8.4"
        errors = record_native_rollout.validate_receipt(receipt)
        self.assertTrue(any("STACK_HOME" in e for e in errors))

    def test_unavailable_result_requires_reason_and_passed_forbids_it(self):
        receipt = valid_receipt()
        receipt["tiers"][1]["unavailable_reason"] = None
        del receipt["tiers"][1]["unavailable_reason"]
        errors = record_native_rollout.validate_receipt(receipt)
        self.assertTrue(any("unavailable_reason is required" in e for e in errors))

        receipt2 = valid_receipt()
        receipt2["tiers"][0]["unavailable_reason"] = "should not be here"
        errors2 = record_native_rollout.validate_receipt(receipt2)
        self.assertTrue(any("must be absent" in e for e in errors2))

    def test_passed_tier_needs_nonempty_commands(self):
        receipt = valid_receipt()
        receipt["tiers"][2]["commands"] = []
        errors = record_native_rollout.validate_receipt(receipt)
        self.assertTrue(any("commands must be nonempty" in e for e in errors))

    def test_duplicate_tier_is_rejected(self):
        receipt = valid_receipt()
        receipt["tiers"].append(valid_tier("T2"))
        errors = record_native_rollout.validate_receipt(receipt)
        self.assertTrue(any("duplicate tier" in e for e in errors))

    def test_private_env_names_must_be_names_not_arbitrary_text(self):
        receipt = valid_receipt()
        # A value-shaped (not NAME-shaped) string must be refused; deliberately not secret-
        # shaped, so it does not also trip scripts/validate.py's own secret-pattern scan.
        receipt["install"]["private_env_names"] = ["not-an-env-var-name-its-lowercase-and-hyphenated"]
        errors = record_native_rollout.validate_receipt(receipt)
        self.assertTrue(any("private_env_names" in e for e in errors))

    def test_retained_native_failures_may_be_empty_but_must_be_a_list(self):
        receipt = valid_receipt()
        receipt["retained_native_failures"] = "none"
        errors = record_native_rollout.validate_receipt(receipt)
        self.assertTrue(any("retained_native_failures" in e for e in errors))

    def test_switch_block_is_optional_but_checked_when_present(self):
        receipt = valid_receipt()
        receipt["switch"] = {"txn": "t1", "ledger_seq": [1, 2], "surfaces": ["current/qmd"], "window": "default"}
        self.assertEqual(record_native_rollout.validate_receipt(receipt), [])
        receipt["switch"]["ledger_seq"] = [1, -2]
        self.assertTrue(record_native_rollout.validate_receipt(receipt))


class QualificationTests(unittest.TestCase):
    def test_qualifies_native_proven_when_t2_t4_t5_pass_and_not_a_service(self):
        evidence_class, reason = record_native_rollout.qualifying_evidence_class(valid_receipt(), service=False)
        self.assertEqual(evidence_class, "native_proven")

    def test_missing_t5_does_not_qualify(self):
        receipt = valid_receipt(tiers=[valid_tier("T0"), valid_tier("T2"), valid_tier("T4")])
        evidence_class, reason = record_native_rollout.qualifying_evidence_class(receipt, service=False)
        self.assertIsNone(evidence_class)
        self.assertIn("T5", reason)

    def test_service_also_requires_t6(self):
        receipt = valid_receipt()
        evidence_class, reason = record_native_rollout.qualifying_evidence_class(receipt, service=True)
        self.assertIsNone(evidence_class)
        self.assertIn("T6", reason)
        receipt["tiers"].append(valid_tier("T6"))
        evidence_class2, _ = record_native_rollout.qualifying_evidence_class(receipt, service=True)
        self.assertEqual(evidence_class2, "native_proven")

    def test_overall_status_not_passed_never_qualifies_even_with_passed_tiers(self):
        receipt = valid_receipt(status="partial")
        evidence_class, reason = record_native_rollout.qualifying_evidence_class(receipt, service=False)
        self.assertIsNone(evidence_class)
        self.assertIn("status", reason)

    def test_a_failed_tier_does_not_qualify(self):
        receipt = valid_receipt(tiers=[valid_tier("T2", "failed", commands=[valid_command(exit=1)]),
                                       valid_tier("T4"), valid_tier("T5")])
        evidence_class, reason = record_native_rollout.qualifying_evidence_class(receipt, service=False)
        self.assertIsNone(evidence_class)

    def test_a_bare_version_probe_t2_does_not_qualify_even_when_passed(self):
        # switch.md requires T2 to be a real workload; scripts/host_receipts.py already draws
        # this same "exactly <program> <flag>" distinction (BARE_HELP_OR_VERSION) for host
        # receipts, and this tool must apply it too rather than accepting a version check as T2.
        receipt = valid_receipt(tiers=[
            {"tier": "T0", "commands": [], "result": "passed"},
            {"tier": "T1", "commands": [], "result": "unavailable", "unavailable_reason": "no GPU"},
            {"tier": "T2", "commands": [valid_command(argv=["qmd", "--version"])], "result": "passed"},
            valid_tier("T4"), valid_tier("T5"),
        ])
        evidence_class, reason = record_native_rollout.qualifying_evidence_class(receipt, service=False)
        self.assertIsNone(evidence_class)
        self.assertIn("bare", reason)

    def test_a_t2_with_at_least_one_real_command_alongside_a_probe_still_qualifies(self):
        receipt = valid_receipt(tiers=[
            valid_tier("T0"), valid_tier("T1", "unavailable", unavailable_reason="no GPU"),
            {"tier": "T2", "result": "passed", "commands": [
                valid_command(argv=["qmd", "--version"]), valid_command(argv=["qmd", "search", "example"])]},
            valid_tier("T4"), valid_tier("T5"),
        ])
        evidence_class, _reason = record_native_rollout.qualifying_evidence_class(receipt, service=False)
        self.assertEqual(evidence_class, "native_proven")

    def test_independent_agreement_other_than_same_result_does_not_qualify(self):
        for agreement in ("different_result", "not_rerun"):
            receipt = valid_receipt()
            receipt["independent"]["agreement"] = agreement
            evidence_class, reason = record_native_rollout.qualifying_evidence_class(receipt, service=False)
            self.assertIsNone(evidence_class, agreement)
            self.assertIn("agreement", reason)


def sample_landscape(*, component_id="qmd", pin="2.8.3"):
    return {
        "schema_version": 2, "checked_at": "2026-09-25", "scope": "foundation",
        "layers": [{
            "catalog": "foundation", "layer_id": "retrieval",
            "winners": [{
                "component_id": component_id, "repository": "https://github.com/example/qmd", "pin": pin,
                "evidence_class": "local_integration", "evidence_refs": ["docs/example.md"],
                "platform_status": {"linux-wsl2-x86_64": "conditional"},
            }],
        }],
    }


class RecordTests(unittest.TestCase):
    def test_qualifying_receipt_updates_the_matching_winner(self):
        receipt = valid_receipt(version="2.8.4")
        landscape = sample_landscape(pin="2.8.4")
        report = record_native_rollout.record(receipt, landscape, catalog="foundation", layer_id="retrieval",
                                              receipt_ref="evidence/receipts/qmd-rollout.json", service=False,
                                              platform="linux-wsl2-x86_64")
        self.assertTrue(report["qualifies"])
        self.assertEqual(report["evidence_class"], "native_proven")
        winner = landscape["layers"][0]["winners"][0]
        self.assertEqual(winner["evidence_class"], "native_proven")
        self.assertIn("evidence/receipts/qmd-rollout.json", winner["evidence_refs"])
        # Without a status_context (no repository evidence supplied), platform_status is left
        # untouched rather than assumed "accepted" from this receipt's own qualifying tiers --
        # see test_platform_status_is_derived_through_scripts_platform_status_not_assumed below
        # for the case where a status_context is given.
        self.assertFalse([c for c in report["changed"] if c.startswith("platform_status")])
        self.assertEqual(winner["platform_status"]["linux-wsl2-x86_64"], "conditional", "left at its original value")

    def test_platform_status_is_derived_through_scripts_platform_status_not_assumed(self):
        # Major finding: record() used to set platform_status[platform] = "accepted" directly,
        # bypassing scripts/platform_status.py, which scripts/landscape.py enforces as a ceiling
        # (macos-arm64 always; a non-grandfathered linux row needs a registered evidence/ ref).
        # A native-rollout receipt alone is not the independently-reviewed host-receipt evidence
        # that ceiling actually requires, so the derivation must run for real, not be skipped.
        receipt = valid_receipt(version="2.8.4")
        landscape = sample_landscape(pin="2.8.4")
        # No bound host receipts at all (empty summary): linux becomes "accepted" only because
        # the evidence_refs entry this call adds is itself a *registered* evidence/ path (the
        # one route record_verdicts.py/platform_status.py already recognise); macos-arm64 has no
        # such route and must stay "untested" even though the receipt qualifies as native_proven.
        context = StatusContext(summary={}, registered_paths=frozenset({"evidence/receipts/qmd-rollout.json"}))
        report = record_native_rollout.record(receipt, landscape, catalog="foundation", layer_id="retrieval",
                                              receipt_ref="evidence/receipts/qmd-rollout.json", service=False,
                                              platform="linux-wsl2-x86_64", status_context=context)
        self.assertTrue(report["qualifies"])
        winner = landscape["layers"][0]["winners"][0]
        self.assertEqual(winner["platform_status"]["linux-wsl2-x86_64"], "accepted")
        self.assertIn("platform_status.linux-wsl2-x86_64", report["changed"])

        landscape2 = sample_landscape(pin="2.8.4")
        report2 = record_native_rollout.record(receipt, landscape2, catalog="foundation", layer_id="retrieval",
                                               receipt_ref="evidence/receipts/qmd-rollout.json", service=False,
                                               platform="macos-arm64", status_context=context)
        self.assertTrue(report2["qualifies"])
        winner2 = landscape2["layers"][0]["winners"][0]
        self.assertEqual(winner2.get("platform_status", {}).get("macos-arm64"), "untested",
                         "a native-rollout receipt alone must never grant macos-arm64 'accepted'")

    def test_a_qualifying_receipt_for_a_new_version_moves_the_pin(self):
        # Brief: record_native_rollout.py "updates a landscape winner's pin[...]". A receipt is
        # the authorization to move the pin to the version it tested, not merely more evidence
        # for whatever the winner's pin already says.
        receipt = valid_receipt(version="2.8.4")
        landscape = sample_landscape(pin="2.8.3")  # winner's current pin is still the old version
        report = record_native_rollout.record(receipt, landscape, catalog="foundation", layer_id="retrieval",
                                              receipt_ref="r.json", service=False, platform="linux-wsl2-x86_64")
        self.assertTrue(report["qualifies"])
        winner = landscape["layers"][0]["winners"][0]
        self.assertEqual(winner["pin"], "2.8.4")
        self.assertIn("pin", report["changed"])

    def test_recording_twice_does_not_duplicate_the_evidence_ref(self):
        receipt = valid_receipt(version="2.8.4")
        landscape = sample_landscape(pin="2.8.4")
        record_native_rollout.record(receipt, landscape, catalog="foundation", layer_id="retrieval",
                                     receipt_ref="evidence/receipts/qmd-rollout.json", service=False,
                                              platform="linux-wsl2-x86_64")
        second = record_native_rollout.record(receipt, landscape, catalog="foundation", layer_id="retrieval",
                                              receipt_ref="evidence/receipts/qmd-rollout.json", service=False,
                                              platform="linux-wsl2-x86_64")
        winner = landscape["layers"][0]["winners"][0]
        self.assertEqual(winner["evidence_refs"].count("evidence/receipts/qmd-rollout.json"), 1)
        self.assertEqual(second["changed"], [])  # already applied; idempotent no-op the second time

    def test_unknown_winner_refuses(self):
        receipt = valid_receipt(component_id="does-not-exist", version="2.8.4")
        landscape = sample_landscape(pin="2.8.4")
        report = record_native_rollout.record(receipt, landscape, catalog="foundation", layer_id="retrieval",
                                              receipt_ref="r.json", service=False, platform="linux-wsl2-x86_64")
        self.assertFalse(report["qualifies"])

    def test_non_qualifying_receipt_leaves_the_winner_untouched(self):
        receipt = valid_receipt(version="2.8.4", tiers=[valid_tier("T2")])  # no T4/T5
        landscape = sample_landscape(pin="2.8.4")
        before = copy.deepcopy(landscape)
        report = record_native_rollout.record(receipt, landscape, catalog="foundation", layer_id="retrieval",
                                              receipt_ref="r.json", service=False, platform="linux-wsl2-x86_64")
        self.assertFalse(report["qualifies"])
        self.assertEqual(landscape, before)


class CLITests(unittest.TestCase):
    def run_cli(self, *args, timeout=30):
        return subprocess.run([sys.executable, str(TOOL_PATH), *args], capture_output=True, text=True, timeout=timeout)

    def test_validate_subcommand_passes_and_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.json"
            good.write_text(json.dumps(valid_receipt()))
            result = self.run_cli("validate", str(good))
            self.assertEqual(result.returncode, 0, result.stderr)

            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"schema_version": 1}))
            result2 = self.run_cli("validate", str(bad))
            self.assertEqual(result2.returncode, 1)
            self.assertIn("kind", result2.stdout)

    def test_record_subcommand_is_report_only_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            receipt_path.write_text(json.dumps(valid_receipt(version="2.8.4")))
            landscape_path = Path(tmp) / "landscape.json"
            original_text = json.dumps(sample_landscape(pin="2.8.4"))
            landscape_path.write_text(original_text)

            result = self.run_cli("record", str(receipt_path), "--landscape", str(landscape_path),
                                  "--catalog", "foundation", "--layer-id", "retrieval",
                                  "--platform", "linux-wsl2-x86_64")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "qualified")
            self.assertEqual(landscape_path.read_text(), original_text, "report-only must not write the file")

            result_write = self.run_cli("record", str(receipt_path), "--landscape", str(landscape_path),
                                        "--catalog", "foundation", "--layer-id", "retrieval",
                                        "--platform", "linux-wsl2-x86_64", "--write")
            self.assertEqual(result_write.returncode, 0, result_write.stderr)
            updated = json.loads(landscape_path.read_text())
            self.assertEqual(updated["layers"][0]["winners"][0]["evidence_class"], "native_proven")

    def test_record_subcommand_exits_3_when_not_qualified(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            receipt_path.write_text(json.dumps(valid_receipt(version="2.8.4", tiers=[valid_tier("T2")])))
            landscape_path = Path(tmp) / "landscape.json"
            landscape_path.write_text(json.dumps(sample_landscape(pin="2.8.4")))

            result = self.run_cli("record", str(receipt_path), "--landscape", str(landscape_path),
                                  "--catalog", "foundation", "--layer-id", "retrieval",
                                  "--platform", "linux-wsl2-x86_64", "--write")
            self.assertEqual(result.returncode, 3)
            self.assertEqual(json.loads(result.stdout)["status"], "not_qualified")

    def test_record_subcommand_refuses_an_invalid_receipt_before_touching_the_landscape(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            receipt_path.write_text(json.dumps({"schema_version": 1}))
            landscape_path = Path(tmp) / "landscape.json"
            original = json.dumps(sample_landscape(pin="2.8.4"))
            landscape_path.write_text(original)

            result = self.run_cli("record", str(receipt_path), "--landscape", str(landscape_path),
                                  "--catalog", "foundation", "--layer-id", "retrieval",
                                  "--platform", "linux-wsl2-x86_64", "--write")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(landscape_path.read_text(), original)


if __name__ == "__main__":
    unittest.main()
