"""Public CLI contracts for W-PROF; source review never becomes host acceptance.

Uses the existing unittest/subprocess contracts in test_adoption_status.py and
test_ecosystem_manifest.py. No installation, provider call or client config read.
"""

import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROFILE = "new-wsl-clean-foundation"
SOURCE = "adoption/new-wsl-profile.json"
HEAD = "85543efe5abcddb7b7cddb14e8774e83b6758616"
CLI = ROOT / "scripts/new_wsl_profile.py"


def run_cli(*args):
    return subprocess.run([sys.executable, str(CLI), *args], capture_output=True,
                          text=True, timeout=30, check=False)


class EmbeddedData(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.active = False
        self.data = ""
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = dict(attrs).get("id") == "ecosystem-data"

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, text):
        if self.active:
            self.data += text


class NewWslProfileCliTests(unittest.TestCase):
    def load(self):
        result = run_cli("--root", str(ROOT), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_generator_adapter_returns_the_full_source_contract(self):
        data = self.load()
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["source_path"], SOURCE)
        self.assertEqual(data["profile_id"], PROFILE)
        self.assertEqual(data["source_head"], HEAD)
        self.assertEqual(data["evidence_class"], "source_review_recommendations")
        self.assertTrue(data["entries"])
        self.assertFalse(data["boundary"]["new_host_acceptance_verified"])

    def test_comparison_arms_are_explicit_and_excluded_from_default_install(self):
        data = self.load()
        by_name = {row["name"]: row for row in data["entries"]}
        for name in ("ColGREP", "BM25", "ripgrep", "gVisor", "boxlite", "sqz",
                     "Headroom", "no compression", "Docker Engine", "Ollama",
                     "Ubuntu 26.04.1 LTS", "Ubuntu 24.04.5 LTS"):
            with self.subTest(name=name):
                arm = by_name[name]
                self.assertEqual(arm["status"], "head-to-head-arm")
                self.assertFalse(arm["default_install"])
                self.assertIsNone(arm["default_precedence"])
        for row in data["entries"]:
            self.assertEqual(row["layer_id"], row["owner_layer_id"])
        self.assertEqual(len(by_name), len(data["entries"]))

    def test_accepted_cli_and_sdk_pins_do_not_assert_sdk_provisioning(self):
        data = self.load()
        rows = {row["name"]: row for row in data["entries"]}
        self.assertEqual(rows["Codex"]["pin"], "0.159.3")
        self.assertEqual(data["boundary"]["accepted_python_sdk_pin"], "0.159.3")
        for name in ("Codex TypeScript SDK", "Codex Python SDK"):
            self.assertEqual(rows[name]["pin"], "0.159.3")
            self.assertEqual(rows[name]["provisioning_status"], "unprovisioned_source_review")
            self.assertFalse(rows[name]["default_install"])

    def fixture_cli(self, data):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / SOURCE
            path.parent.mkdir()
            path.write_text(json.dumps(data), encoding="utf-8")
            return run_cli("--root", str(root), "--json")

    def test_explicit_missing_evidence_survives_the_adapter(self):
        data = self.load()
        row = data["entries"][0]
        row["checksum"] = {"algorithm": None, "value": None, "source": None, "kind": None}
        row["acceptance"] = {"command": None, "source": None, "evidence_class": None}
        row["blocking_gaps"] = ["Checksum and upstream acceptance remain unverified."]
        result = self.fixture_cli(data)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        returned = json.loads(result.stdout)["entries"][0]
        self.assertIsNone(returned["checksum"]["value"])
        self.assertIsNone(returned["acceptance"]["command"])
        self.assertEqual(returned["blocking_gaps"], row["blocking_gaps"])

    def test_missing_evidence_without_a_gap_is_rejected(self):
        data = self.load()
        data["entries"][0]["checksum"]["value"] = None
        data["entries"][0]["blocking_gaps"] = []
        result = self.fixture_cli(data)
        self.assertEqual(result.returncode, 2)

    def test_multiple_owners_and_false_host_acceptance_are_rejected(self):
        data = self.load()
        mutations = []
        duplicate = copy.deepcopy(data)
        duplicate["entries"].append(copy.deepcopy(duplicate["entries"][0]))
        duplicate["entries"][-1]["owner_layer_id"] = "workers"
        mutations.append(duplicate)
        accepted = copy.deepcopy(data)
        accepted["boundary"]["new_host_acceptance_verified"] = True
        mutations.append(accepted)
        for changed in mutations:
            result = self.fixture_cli(changed)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_native_prerequisite_cli_carries_source_review_boundaries(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/adoption_status.py"), "--repo-root", str(ROOT),
             "--manifest", str(ROOT / "adoption/manifest.json"), "--profile", PROFILE, "--json"],
            capture_output=True, text=True, timeout=30, check=False)
        self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["errors"], [])
        self.assertFalse(data["runtime_acceptance_verified"])
        source = data["profiles"][0]["source_profile"]
        self.assertEqual(source["path"], SOURCE)
        self.assertEqual(source["evidence_class"], "source_review_recommendations")
        self.assertGreater(source["entries_with_blocking_gaps"], 0)

    def test_existing_public_generator_preserves_the_native_profile_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ecosystem.html"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_ecosystem.py"), "--root", str(ROOT),
                 "--render-to", str(output)], capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(EmbeddedData(output.read_text(encoding="utf-8")).data)
        profile = next(row for row in data["setup"]["profiles"] if row["id"] == PROFILE)
        self.assertEqual(profile["source_profile"], SOURCE)
        self.assertEqual(profile["component_ids"], ["codex", "claude-code"])


if __name__ == "__main__":
    unittest.main()
