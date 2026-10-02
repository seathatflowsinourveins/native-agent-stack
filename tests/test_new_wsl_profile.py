"""Public CLI contracts for W-PROF; source review never becomes host acceptance.

Uses the existing unittest/subprocess contracts in test_adoption_status.py and
test_ecosystem_manifest.py. No installation, provider call or client config read.
"""

import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROFILE = "new-wsl-clean-foundation"
SOURCE = "adoption/new-wsl-profile.json"
HEAD = "85543efe5abcddb7b7cddb14e8774e83b6758616"
CLI = ROOT / "scripts/new_wsl_profile.py"
DEFAULTS_SOURCE = "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json"


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
                     "Ubuntu 26.04.1 LTS", "Ubuntu 24.04.5 LTS", "ai-memory",
                     "Hindsight", "agentmemory", "deja-vu"):
            with self.subTest(name=name):
                arm = by_name[name]
                self.assertEqual(arm["status"], "head-to-head-arm")
                self.assertFalse(arm["default_install"])
                self.assertIsNone(arm["default_precedence"])
        for row in data["entries"]:
            self.assertEqual(row["layer_id"], row["owner_layer_id"])
        self.assertEqual(len(by_name), len(data["entries"]))
        self.assert_no_unmeasured_defaults(data)

    def assert_no_unmeasured_defaults(self, data):
        manifest = json.loads((ROOT / DEFAULTS_SOURCE).read_text())
        for slot in manifest["slots"]:
            if slot.get("state") in {"split", "measurement"}:
                arms = [row for row in data["entries"] if row["layer_id"] == slot["layer_id"]
                        and (row.get("comparison_group") or row["status"] == "head-to-head-arm")]
                self.assertTrue(arms, slot["slot_id"])
                for row in arms:
                    self.assertFalse(row["default_install"], row["name"] + " in " + slot["slot_id"])

    def test_negative_control_memory_cannot_become_a_default_before_measurement(self):
        data = self.load()
        row = next(row for row in data["entries"] if row["name"] == "ai-memory")
        row.update(status="picked", default_install=True)
        with self.assertRaisesRegex(AssertionError, "ai-memory.*memory-owner"):
            self.assert_no_unmeasured_defaults(data)
        result = self.fixture_cli(data)
        self.assertEqual(result.returncode, 2)
        self.assertIn("memory-owner", result.stderr)
        self.assertIn("ai-memory", result.stderr)

    def test_every_unresolved_slot_arm_is_rejected_as_a_default_even_when_picked(self):
        original = self.load()
        manifest = json.loads((ROOT / DEFAULTS_SOURCE).read_text())
        unresolved = {slot["layer_id"] for slot in manifest["slots"]
                      if slot.get("state") in {"split", "measurement"}}
        for index, row in enumerate(original["entries"]):
            if row["layer_id"] in unresolved and row.get("comparison_group"):
                with self.subTest(name=row["name"]):
                    data = copy.deepcopy(original)
                    data["entries"][index].update(status="picked", default_install=True)
                    result = self.fixture_cli(data)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(row["name"], result.stderr)

    def test_entries_follow_one_version_drift_rule(self):
        data = self.load()
        claude = next(row for row in data["entries"] if row["name"] == "Claude Code")
        rule = claude["version_policy"]
        for phrase in ("last qualified release", "floor", "current at install time", "receipt",
                       "installed version", "installed and not yet qualified", "acceptance command",
                       "passed on that host"):
            self.assertIn(phrase, rule)
        self.assertTrue(claude["install"]["command"].endswith("bash -s latest"))
        for row in data["entries"]:
            text = json.dumps(row)
            self.assertIsNone(re.search(r"Installed host .*?\b(?:does|do) not qualify\b.*?selected", text), row["name"])
            if "floor" in text:
                self.assertNotRegex(text, r"\b(?:does|do) not qualify\b")
        bootstrap = (ROOT / "adoption/bootstrap.md").read_text()
        self.assertIn(rule, " ".join(bootstrap.split()))
        overview = (ROOT / "adoption/new-wsl-profile.md").read_text()
        self.assertIn(rule, " ".join(overview.split()))

    def test_negative_control_floor_rule_cannot_reject_a_newer_installed_release(self):
        data = self.load()
        row = next(row for row in data["entries"] if row["name"] == "Claude Code")
        row["acceptance"]["scope"] += " Installed host 2.1.287 does not qualify selected 2.1.284."
        result = self.fixture_cli(data)
        self.assertEqual(result.returncode, 2)
        self.assertIn("version floor", result.stderr)

    def test_rootless_engine_and_boundary_have_unrun_acceptance_and_host_gate(self):
        data = self.load()
        rows = {row["name"]: row for row in data["entries"]}
        for name in ("Docker Engine", "rootless container boundary"):
            row = rows[name]
            acceptance = row["acceptance"]
            self.assertFalse(row["default_install"])
            self.assertEqual(acceptance["execution_status"], "UNRUN")
            self.assertEqual(acceptance["evidence_class"], "documented_upstream_example_not_executed")
            for fragment in ("docker info", "SecurityOptions", "rootless", "docker run --rm hello-world"):
                self.assertIn(fragment, acceptance["command"])
            self.assertEqual(acceptance["source"], "https://docs.docker.com/engine/security/rootless/")
            self.assertIn("user-level daemon", " ".join(acceptance["prerequisites"]))
            self.assertIn("41492", json.dumps(row))
            self.assertIn("first run on the new host", " ".join(row["blocking_gaps"]))
        prerequisites = json.dumps(data["host_prerequisites"])
        for fragment in ("3.0.1", "2.7.x", "40519", "41512", "adoption/platforms/linux-wsl2-new-distro.md"):
            self.assertIn(fragment, prerequisites)

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
            manifest = root / DEFAULTS_SOURCE
            manifest.parent.mkdir(parents=True)
            manifest.write_bytes((ROOT / DEFAULTS_SOURCE).read_bytes())
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
