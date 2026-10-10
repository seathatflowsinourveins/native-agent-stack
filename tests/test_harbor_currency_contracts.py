"""Harbor source/maintenance contracts; no installation or provider execution.

CPython v3.13.16 accepts any matching exception inside assertRaises:
https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/case.py#L253-L278
Retrieve, hash-check and parse historical inputs before expecting content rejection.
The retained bytes declare PR #927 pre-squash provenance, not a repository pin.
The fixtures also work after squash merging or in a Git-free archive.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PLAN = "evidence/artifacts/new-wsl-install-plan-20261002"
DECISION = "docs/decisions/2026-10-09-harbor-0240-profile.md"
PROFILE = "adoption/new-wsl-profile.json"
CONSENSUS = "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json"
AUTHORITY = "the coordinator's 2026-10-09 currency amendment under the owner's standing direction to keep tools current"
PRE_SQUASH_PROVENANCE = {
    "kind": "pr-branch-pre-squash",
    "pull_request": 927,
    "commit": "b67a28264d84c9e9b51e0671ee1db046270ff833",
}
PREDECESSOR_FIXTURES = Path(__file__).resolve().parent / "fixtures/harbor_currency_predecessors"


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
        manifest = json.loads((PREDECESSOR_FIXTURES / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertNotIn("source_revision", manifest, "pre-squash provenance is not a repository pin")
        self.assertEqual(manifest["provenance"], PRE_SQUASH_PROVENANCE)
        rows = [row for row in manifest["fixtures"] if row["source_path"] == path]
        self.assertEqual(len(rows), 1, "predecessor fixture declaration missing or ambiguous: " + path)
        row, = rows
        raw = (PREDECESSOR_FIXTURES / row["fixture"]).read_bytes()
        self.assertEqual(len(raw), row["bytes"], "predecessor fixture length mismatch: " + path)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"],
                         "predecessor fixture SHA-256 mismatch: " + path)
        header = f"blob {len(raw)}\0".encode("ascii")
        self.assertEqual(hashlib.sha1(header + raw).hexdigest(), row["git_blob"],
                         "predecessor fixture Git blob mismatch: " + path)
        return raw.decode("utf-8")

    def test_current_readme_routes_harbor_to_its_receipt_and_qualifies_history(self):
        self.readme_contract((ROOT / PLAN / "README.md").read_text())

    def test_predecessor_readme_fails_the_source_routing_guard(self):
        text = self.predecessor(PLAN + "/README.md")
        with self.assertRaisesRegex(AssertionError, r"Regex didn't match:.*SOURCES.*0.*23.*history"):
            self.readme_contract(text)

    def test_inverse_names_every_operative_carrier(self):
        self.inverse_contract((ROOT / DECISION).read_text())

    def test_predecessor_profile_only_inverse_fails_the_inventory_guard(self):
        text = self.predecessor(DECISION)
        with self.assertRaisesRegex(AssertionError, r"adoption/new-wsl-profile\.json.*not found"):
            self.inverse_contract(text)

    def test_current_owner_release_is_bound_and_retained_metadata_is_historical(self):
        self.owners_contract(json.loads((ROOT / PLAN / "owners.json").read_text()))

    def test_predecessor_empty_note_fails_the_snapshot_guard(self):
        document = json.loads(self.predecessor(PLAN + "/owners.json"))
        with self.assertRaisesRegex(AssertionError, r"Regex didn't match:.*pushed_at.*historical"):
            self.owners_contract(document)

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


class HarborPredecessorEvidenceTests(unittest.TestCase):
    CASES = (
        ("test_predecessor_readme_fails_the_source_routing_guard", "readme_contract", PLAN + "/README.md"),
        ("test_predecessor_profile_only_inverse_fails_the_inventory_guard", "inverse_contract", DECISION),
        ("test_predecessor_empty_note_fails_the_snapshot_guard", "owners_contract", PLAN + "/owners.json"),
    )

    def test_manifest_revision_is_main_reachable_or_declared_pre_squash(self):
        manifest = json.loads((PREDECESSOR_FIXTURES / "manifest.json").read_text(encoding="utf-8"))
        provenance = manifest.get("provenance", {})
        if provenance.get("kind") == "pr-branch-pre-squash":
            self.assertNotIn("source_revision", manifest,
                             "pre-squash provenance must not also declare a repository pin")
            self.assertEqual(provenance["pull_request"], 927)
            self.assertRegex(provenance["commit"], r"^[0-9a-f]{40}$")
            self.assertEqual(manifest["capture_status"], "already-run-on-pr-branch-before-squash")
            self.assertEqual(manifest["capture_command"], "git show <provenance.commit>:<source_path>")
            return

        revision = manifest["source_revision"]
        if shutil.which("git") is None:
            self.skipTest("Git unavailable; repository-pin ancestry cannot be measured")
        history = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--verify", "refs/remotes/origin/main^{commit}"],
            capture_output=True, text=True,
        )
        if history.returncode != 0:
            self.skipTest("origin/main history unavailable in this checkout or Git-free archive")
        reachable = subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", revision, "origin/main"],
            capture_output=True, text=True,
        )
        self.assertEqual(reachable.returncode, 0,
                         "fixture repository revision must be reachable from origin/main; "
                         "retained PR capture bytes require explicit pr-branch-pre-squash provenance")

    def test_mismatched_git_blob_cannot_satisfy_semantic_rejection(self):
        for name, guard_name, source_path in self.CASES:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                fixture_root = Path(temporary) / "predecessors"
                shutil.copytree(PREDECESSOR_FIXTURES, fixture_root)
                manifest_path = fixture_root / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                row, = [row for row in manifest["fixtures"] if row["source_path"] == source_path]
                row["git_blob"] = "0" * 40
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                case = HarborCurrencyContracts(name)
                result = unittest.TestResult()
                with mock.patch(__name__ + ".PREDECESSOR_FIXTURES", fixture_root), \
                        mock.patch.object(case, guard_name, side_effect=AssertionError("semantic rejection")) as guard:
                    case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.wasSuccessful(), "incorrect Git blob was accepted as semantic evidence")
                self.assertEqual(len(result.failures) + len(result.errors), 1)
                self.assertIn("predecessor fixture Git blob mismatch", (result.failures + result.errors)[0][1])
                guard.assert_not_called()

    def test_wrong_guard_message_cannot_satisfy_semantic_rejection(self):
        for name, guard_name, _ in self.CASES:
            with self.subTest(case=name):
                case = HarborCurrencyContracts(name)
                result = unittest.TestResult()
                message = "unrelated guard failure"
                with mock.patch.object(case, guard_name, side_effect=AssertionError(message)) as guard:
                    case.run(result)
                guard.assert_called_once()
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.wasSuccessful(), "unrelated failure was accepted as the targeted guard")
                self.assertEqual(len(result.failures) + len(result.errors), 1)
                self.assertIn(message, (result.failures + result.errors)[0][1])

    def test_retrieval_failure_cannot_satisfy_semantic_rejection(self):
        for name, guard_name, _ in self.CASES:
            with self.subTest(case=name):
                case = HarborCurrencyContracts(name)
                result = unittest.TestResult()
                message = "predecessor input unavailable"
                with mock.patch.object(case, "predecessor", side_effect=AssertionError(message)) as retrieve, \
                        mock.patch.object(case, guard_name, side_effect=AssertionError("semantic rejection")) as guard:
                    case.run(result)
                retrieve.assert_called_once()
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.wasSuccessful(), "retrieval failure was accepted as semantic evidence")
                self.assertEqual(len(result.failures) + len(result.errors), 1)
                self.assertIn(message, (result.failures + result.errors)[0][1])
                guard.assert_not_called()

    def test_missing_or_corrupt_fixture_cannot_satisfy_semantic_rejection(self):
        for name, guard_name, source_path in self.CASES:
            for mode in ("missing", "corrupt"):
                with self.subTest(case=name, mode=mode), tempfile.TemporaryDirectory() as temporary:
                    fixture_root = Path(temporary) / "predecessors"
                    shutil.copytree(PREDECESSOR_FIXTURES, fixture_root)
                    manifest = json.loads((fixture_root / "manifest.json").read_text())
                    row, = [row for row in manifest["fixtures"] if row["source_path"] == source_path]
                    fixture = fixture_root / row["fixture"]
                    if mode == "missing":
                        fixture.unlink()
                        expected_failure = "FileNotFoundError"
                    else:
                        raw = fixture.read_bytes()
                        corrupted = raw.replace(b" ", b"\t", 1)
                        self.assertNotEqual(raw, corrupted)
                        self.assertEqual(len(raw), len(corrupted))
                        fixture.write_bytes(corrupted)
                        expected_failure = "predecessor fixture SHA-256 mismatch"
                    case = HarborCurrencyContracts(name)
                    result = unittest.TestResult()
                    with mock.patch(__name__ + ".PREDECESSOR_FIXTURES", fixture_root), \
                            mock.patch.object(case, guard_name, side_effect=AssertionError("semantic rejection")) as guard:
                        case.run(result)
                    self.assertEqual(result.testsRun, 1)
                    self.assertFalse(result.wasSuccessful(), "fixture failure was accepted as semantic evidence")
                    self.assertEqual(len(result.failures) + len(result.errors), 1)
                    self.assertIn(expected_failure, (result.failures + result.errors)[0][1])
                    guard.assert_not_called()


if __name__ == "__main__":
    unittest.main()
