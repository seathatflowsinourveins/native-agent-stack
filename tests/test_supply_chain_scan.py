"""Check the recorded supply-chain vulnerability-scan receipt is self-consistent.

This does not re-run Syft or Grype. It verifies the receipt JSON parses,
every finding carries a disposition and a non-empty reason, the recorded
finding counts match the disposition table, and either the referenced raw
scan-output files exist on disk or the receipt records their exact byte
count and SHA-256 (the accepted alternative when raw outputs are kept
outside the repository, as documented in the receipt itself).
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    ROOT
    / "blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json"
)

ALLOWED_DISPOSITIONS = {"upstream_pinned", "runtime_only", "needs_review"}
FORBIDDEN_REASON_PHRASES = ("accepted risk",)


def load_receipt() -> dict:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


class SupplyChainScanReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt = load_receipt()

    def test_receipt_parses_and_has_required_top_level_fields(self) -> None:
        for field in (
            "schema_version",
            "id",
            "kind",
            "observed_at_utc",
            "status",
            "claim",
            "evidence_class",
            "scope",
            "tooling",
            "commands",
            "inventory",
            "findings",
            "raw_artifacts",
            "limitations",
        ):
            self.assertIn(field, self.receipt, f"receipt missing {field!r}")

    def test_evidence_class_is_native_proven_for_the_scan(self) -> None:
        self.assertEqual(self.receipt["evidence_class"], "native_proven")

    def test_every_command_has_an_exit_code_and_it_is_zero(self) -> None:
        commands = self.receipt["commands"]
        self.assertGreaterEqual(len(commands), 4)
        for entry in commands:
            self.assertIn("command", entry)
            self.assertIn("exit_code", entry)
            self.assertEqual(
                entry["exit_code"], 0, f"non-zero exit recorded for {entry['command']!r}"
            )

    def test_findings_every_row_has_disposition_and_nonempty_reason(self) -> None:
        findings = self.receipt["findings"]
        table = findings["disposition_table"]
        self.assertIsInstance(table, list)
        for row in table:
            for field in ("package", "version", "id", "severity", "fix_state", "disposition", "reason"):
                self.assertIn(field, row, f"disposition row missing {field!r}: {row}")
            self.assertIn(
                row["disposition"],
                ALLOWED_DISPOSITIONS,
                f"unexpected disposition {row['disposition']!r}",
            )
            reason = row["reason"]
            self.assertIsInstance(reason, str)
            self.assertTrue(reason.strip(), "disposition reason must not be empty")
            lowered = reason.lower()
            for phrase in FORBIDDEN_REASON_PHRASES:
                self.assertNotIn(
                    phrase, lowered, f"disposition reason must not be a bare {phrase!r}"
                )

    def test_finding_counts_match_disposition_table_length(self) -> None:
        findings = self.receipt["findings"]
        table = findings["disposition_table"]
        self.assertEqual(
            findings["total_matches"],
            findings["runtime_grype_matches"] + findings["adapter_grype_matches"],
        )
        self.assertEqual(
            len(table),
            findings["total_matches"],
            "disposition table row count must equal total recorded matches",
        )
        severity_total = sum(findings["by_severity"].values())
        self.assertEqual(
            severity_total,
            findings["total_matches"],
            "severity breakdown must sum to total matches",
        )

    def test_raw_artifact_references_exist_or_are_hash_recorded(self) -> None:
        raw = self.receipt["raw_artifacts"]
        files = raw["files"]
        self.assertGreater(len(files), 0)
        total_bytes = 0
        for entry in files:
            self.assertIn("name", entry)
            self.assertIn("bytes", entry)
            self.assertIn("sha256", entry)
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertIsInstance(entry["bytes"], int)
            self.assertGreater(entry["bytes"], 0)
            total_bytes += entry["bytes"]

            # The raw file may exist directly inside this receipt's directory
            # (small-output case) or be recorded by hash only, with the raw
            # bytes kept outside the repository (this receipt's case, per
            # raw_artifacts.storage_note). Either is acceptable; if the file
            # is present in-repo its hash must match exactly.
            candidate = RECEIPT_PATH.parent / entry["name"]
            if candidate.exists():
                digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
                self.assertEqual(digest, entry["sha256"])
                self.assertEqual(candidate.stat().st_size, entry["bytes"])

        self.assertEqual(total_bytes, raw["total_bytes"])

    def test_receipt_contains_no_personal_home_path(self) -> None:
        # Mirrors scripts/validate.py's publication private-content scan so
        # this specific, known-risky receipt does not regress silently.
        content = RECEIPT_PATH.read_text(encoding="utf-8")
        pattern = re.compile(r"/(?:home|Users)/(?!example(?:/|\b))[A-Za-z0-9_.-]+(?:/|\b)")
        match = pattern.search(content)
        self.assertIsNone(match, f"receipt contains a personal path fragment: {match}")

    def test_package_inventory_counts_match_declared_totals(self) -> None:
        inventory = self.receipt["inventory"]
        runtime = inventory["runtime_scan"]
        adapter = inventory["adapter_scan"]
        self.assertEqual(runtime["syft_packages"], len(runtime["packages"]))
        self.assertEqual(adapter["syft_packages"], len(adapter["packages"]))

        runtime_names = {pkg["name"] for pkg in runtime["packages"]}
        adapter_names = {pkg["name"] for pkg in adapter["packages"]}
        self.assertIn("nautilus-trader", runtime_names)
        self.assertIn("alpaca-py", runtime_names)
        self.assertTrue(adapter_names.issubset(runtime_names))

        runtime_versions = {pkg["name"]: pkg["version"] for pkg in runtime["packages"]}
        for pkg in adapter["packages"]:
            self.assertEqual(
                pkg["version"],
                runtime_versions[pkg["name"]],
                f"adapter pin for {pkg['name']} does not match runtime installed version",
            )


if __name__ == "__main__":
    unittest.main()
