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
import json
import subprocess
import sys
import textwrap
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CATALOG_FRESHNESS = ROOT / ".github/workflows/catalog-freshness.yml"
VALIDATE = ROOT / ".github/workflows/validate.yml"
SUPPLY_CHAIN = ROOT / ".github/workflows/supply-chain.yml"
REQUIREMENTS_LOCK = ROOT / ".github/requirements-ci.txt"


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
        self.assertIsNotNone(match, "requirements-ci.txt no longer pins zizmor")
        self.assertEqual(table_pin, match.group(1))


class PrereleasePinSummaryTests(unittest.TestCase):
    """Execute the workflow's Python summary read with synthetic gh responses."""

    def test_summary_uses_the_same_bounded_stream_policy_as_the_manifest(self):
        workflow = CATALOG_FRESHNESS.read_text()
        match = re.search(r"latest=\$\(python3 - .*?<<'PYEOF'\n(.*?)\n\s*PYEOF", workflow, re.DOTALL)
        self.assertIsNotNone(match, "the fixed-pin summary must use the shared release-stream policy")
        source = textwrap.dedent(match.group(1))

        def release(tag, *, draft=False, published_at="2026-10-04T00:00:00Z", prerelease=True):
            return {"tag_name": tag, "draft": draft, "published_at": published_at, "prerelease": prerelease}

        backport = release("v1.231.1", published_at="2026-10-05T00:00:00Z", prerelease=False)
        cases = (
            ("rc6", "2.0.0rc5", [[release("v2.0.0rc6")]], "v2.0.0rc6", 1),
            ("backport on first page", "2.0.0rc5", [[backport] * 100, [release("v2.0.0rc6")]], "v2.0.0rc6", 2),
            ("draft", "2.0.0rc5", [[release("v2.0.0rc7", draft=True), release("v2.0.0rc6")]], "v2.0.0rc6", 1),
            ("cap", "2.0.0rc5", [[backport] * 100] * 3, "unknown beyond cap", 3),
            ("stable", "1.230.0", [], "v1.231.0", 0),
        )
        for name, pin, pages, expected, expected_pages in cases:
            calls = []

            def gh(command, **kwargs):
                self.assertEqual(command[:2], ["gh", "api"])
                self.assertEqual(len(command), 3, "gh --paginate would bypass the page cap")
                path = command[2]
                calls.append(path)
                if path.endswith("/releases/latest"):
                    data = release("v1.231.0", prerelease=False)
                else:
                    self.assertIn("/releases?per_page=100&page=", path)
                    page = int(path.rsplit("=", 1)[1])
                    self.assertLessEqual(page, 3)
                    data = pages[page - 1]
                return subprocess.CompletedProcess(command, 0, json.dumps(data), "")

            with self.subTest(case=name), mock.patch("subprocess.run", side_effect=gh), \
                    mock.patch.object(sys, "argv", ["-", "nautechsystems/nautilus_trader", pin]), \
                    mock.patch.object(sys, "path", [*sys.path]), redirect_stdout(StringIO()) as output:
                exec(compile(source, str(CATALOG_FRESHNESS), "exec"), {"__name__": "__main__"})
                self.assertEqual(output.getvalue().strip(), expected)
                self.assertEqual(sum("/releases?" in call for call in calls), expected_pages)


if __name__ == "__main__":
    unittest.main()
