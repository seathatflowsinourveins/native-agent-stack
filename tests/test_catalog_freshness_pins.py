"""Regression coverage tying catalog-freshness.yml's fixed-tool pin table to
the actual pins declared elsewhere in the repository.

A prior change silently excluded grype from this table, and the doc text
that grew up around that exclusion asserted grype "tracks upstream's latest
release" when in fact supply-chain.yml pins and checksum-verifies an exact
grype version just like the other four tools. This module checks the
freshness table's spec list directly against each tool's declared pin so a
future edit cannot drop a tool from the table, or let its pinned version
drift from the workflow that actually downloads and verifies the binary,
without failing `python3 -m unittest`.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_FRESHNESS = ROOT / ".github/workflows/catalog-freshness.yml"
VALIDATE = ROOT / ".github/workflows/validate.yml"
SUPPLY_CHAIN = ROOT / ".github/workflows/supply-chain.yml"
REQUIREMENTS_LOCK = ROOT / ".github/requirements-ci.lock"


def _freshness_spec_table() -> dict[str, tuple[str, str]]:
    """Parse the `name|owner/repo|pinned` spec entries out of the freshness
    workflow's "Append the fixed CI-tool pin-drift table" step.

    Returns {name: (repo, pinned_version)}.
    """
    text = CATALOG_FRESHNESS.read_text()
    specs = re.findall(r'"([\w.-]+)\|([\w.-]+/[\w.-]+)\|([^"]+)"', text)
    return {name: (repo, pinned) for name, repo, pinned in specs}


class CatalogFreshnessPinTableTests(unittest.TestCase):
    def setUp(self):
        self.table = _freshness_spec_table()

    def test_table_covers_all_five_fixed_binary_pins_plus_nautilus_trader(self):
        self.assertEqual(
            set(self.table),
            {"actionlint", "gitleaks", "syft", "zizmor", "grype", "nautilus_trader"},
            "catalog-freshness.yml's fixed-tool pin table dropped or gained an "
            "entry; every fixed CI binary pin (actionlint, gitleaks, syft, "
            "zizmor, grype) plus nautilus_trader must stay listed so freshness "
            "drift is checked for all of them, not a subset.",
        )

    def test_grype_pin_matches_supply_chain_workflow(self):
        _, table_pin = self.table["grype"]
        supply_chain_text = SUPPLY_CHAIN.read_text()
        match = re.search(r"GRYPE_VERSION:\s*'([^']+)'", supply_chain_text)
        self.assertIsNotNone(match, "supply-chain.yml no longer declares GRYPE_VERSION")
        self.assertEqual(
            table_pin, match.group(1),
            "catalog-freshness.yml's grype pin drifted from the checksum-verified "
            "pin supply-chain.yml actually downloads",
        )

    def test_syft_pin_matches_supply_chain_workflow(self):
        _, table_pin = self.table["syft"]
        supply_chain_text = SUPPLY_CHAIN.read_text()
        match = re.search(r"SYFT_VERSION:\s*'([^']+)'", supply_chain_text)
        self.assertIsNotNone(match, "supply-chain.yml no longer declares SYFT_VERSION")
        self.assertEqual(table_pin, match.group(1))

    def test_gitleaks_pin_matches_validate_workflow(self):
        _, table_pin = self.table["gitleaks"]
        validate_text = VALIDATE.read_text()
        match = re.search(r"GITLEAKS_VERSION:\s*'([^']+)'", validate_text)
        self.assertIsNotNone(match, "validate.yml no longer declares GITLEAKS_VERSION")
        self.assertEqual(table_pin, match.group(1))

    def test_actionlint_pin_matches_validate_workflow(self):
        _, table_pin = self.table["actionlint"]
        validate_text = VALIDATE.read_text()
        match = re.search(r"ACTIONLINT_VERSION:\s*'([^']+)'", validate_text)
        self.assertIsNotNone(match, "validate.yml no longer declares ACTIONLINT_VERSION")
        self.assertEqual(table_pin, match.group(1))

    def test_zizmor_pin_matches_requirements_lock(self):
        _, table_pin = self.table["zizmor"]
        lock_text = REQUIREMENTS_LOCK.read_text()
        match = re.search(r"zizmor==([\w.]+)", lock_text)
        self.assertIsNotNone(match, "requirements-ci.lock no longer pins zizmor")
        self.assertEqual(table_pin, match.group(1))


if __name__ == "__main__":
    unittest.main()
