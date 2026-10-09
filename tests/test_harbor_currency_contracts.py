"""Harbor source/maintenance contracts; no installation or provider execution."""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAN = "evidence/artifacts/new-wsl-install-plan-20261002"
DECISION = "docs/decisions/2026-10-09-harbor-0240-profile.md"
PROFILE = "adoption/new-wsl-profile.json"
CONSENSUS = "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json"
AUTHORITY = "the coordinator's 2026-10-09 currency amendment under the owner's standing direction to keep tools current"


class HarborCurrencyContracts(unittest.TestCase):
    def profile(self):
        return next(row for row in json.loads((ROOT / PROFILE).read_text())["entries"] if row["name"] == "Harbor")

    def readme_contract(self, text):
        paragraph = text.split("## G5 analytics and evaluation acceptance (2026-10-04)", 1)[1].lstrip().split("\n\n", 1)[0]
        receipt = self.profile()["install"]["source_review_ref"]
        target = "../" + str(Path(receipt).relative_to("evidence/artifacts"))
        self.assertIn("](" + target + ")", paragraph)
        self.assertIn("Harbor " + self.profile()["pin"], paragraph)
        self.assertRegex(paragraph, r"SOURCES\.md.*(?:original|dated).*0\.23\.0.*history")

    def inverse_contract(self, text):
        inverse = text.split("The inverse restores", 1)[1]
        # Approved operative carrier inventory, separate from generated copies.
        required = (PROFILE, "adoption/new-wsl-profile.md", "consensus.json", "definitive-manifest.json",
                    "install-plan.json", "owners.json", "install.sh:1034,1036", "accept.sh:2726",
                    "README.md", "harbor-worker-telemetry-accept.sh", "harbor-worker-telemetry-contract.md",
                    "install.sh:1136")
        for carrier in required:
            self.assertIn(carrier, inverse, carrier)
        for source in (PROFILE, "adoption/new-wsl-profile.md", PLAN + "/install-plan.json",
                       PLAN + "/owners.json", PLAN + "/install.sh", PLAN + "/accept.sh",
                       PLAN + "/config/harbor-worker-telemetry-accept.sh", PLAN + "/config/harbor-worker-telemetry-contract.md"):
            self.assertTrue((ROOT / source).is_file(), source)

    def owners_contract(self, document):
        owner = next(row for row in document["owners"] if row["slot"] == "harbor-containerized-agent-e2e-runner")
        release = json.loads((ROOT / owner["current_release_source"]).read_text())
        self.assertEqual(owner["tag_name"], release["tag_name"])
        self.assertEqual(owner["published_at"], release["published_at"])
        self.assertLess(owner["pushed_at"], owner["published_at"])
        self.assertRegex(owner["note"], r"(?:pushed_at.*historical|historical.*pushed_at)")
        self.assertIn("default_branch", owner["note"])
        self.assertIn("current_release_source", owner["note"])

    def predecessor(self, path):
        result = subprocess.run(["git", "show", "b67a28264d84c9e9b51e0671ee1db046270ff833:" + path],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_current_readme_routes_harbor_to_its_receipt_and_qualifies_history(self):
        self.readme_contract((ROOT / PLAN / "README.md").read_text())

    def test_predecessor_readme_fails_the_source_routing_guard(self):
        with self.assertRaises(AssertionError):
            self.readme_contract(self.predecessor(PLAN + "/README.md"))

    def test_inverse_names_every_operative_carrier(self):
        self.inverse_contract((ROOT / DECISION).read_text())

    def test_predecessor_profile_only_inverse_fails_the_inventory_guard(self):
        with self.assertRaises(AssertionError):
            self.inverse_contract(self.predecessor(DECISION))

    def test_current_owner_release_is_bound_and_retained_metadata_is_historical(self):
        self.owners_contract(json.loads((ROOT / PLAN / "owners.json").read_text()))

    def test_predecessor_empty_note_fails_the_snapshot_guard(self):
        with self.assertRaises(AssertionError):
            self.owners_contract(json.loads(self.predecessor(PLAN + "/owners.json")))

    def test_profile_markdown_contains_the_actual_harbor_source_contract(self):
        row = self.profile()
        text = (ROOT / "adoption/new-wsl-profile.md").read_text()
        self.assertRegex(text, r"\| Harbor \| " + re.escape(row["pin"]) + r" \|")
        for value in (row["install"]["command"], row["install"]["source"], row["acceptance"]["command"],
                      row["acceptance"]["source"], row["checksum"]["value"]):
            self.assertIn(value, text)

    def test_maintenance_authority_is_the_coordinator_under_the_standing_rule(self):
        entry, = json.loads((ROOT / CONSENSUS).read_text())["current_owner_pin_amendments"]
        self.assertEqual(entry["by"], AUTHORITY)
        manifest = json.loads((ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json").read_text())
        row = next(row for row in manifest["slots"] if row["slot_id"] == "trajectory-analysis")
        self.assertEqual(row["current_owner_pin_amendment"]["by"], AUTHORITY)


if __name__ == "__main__":
    unittest.main()
