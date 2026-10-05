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
REHEARSAL_RECORD = "evidence/artifacts/new-wsl-rehearsal-20261002/runs-on-wsl-3.0.1.json"


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
                     "no compression", "Docker Engine", "Ollama",
                     "Ubuntu 26.04.1 LTS", "Ubuntu 24.04.5 LTS", "ai-memory",
                     "Hindsight", "agentmemory", "deja-vu", "SocratiCode", "semble"):
            with self.subTest(name=name):
                arm = by_name[name]
                self.assertEqual(arm["status"], "head-to-head-arm")
                self.assertFalse(arm["default_install"])
                self.assertIsNone(arm["default_precedence"])
        for row in data["entries"]:
            self.assertEqual(row["layer_id"], row["owner_layer_id"])
        self.assertEqual(len(by_name), len(data["entries"]))
        self.assert_no_unmeasured_defaults(data)

    def test_owner_defaults_of_the_token_layer_are_picked_and_installed_by_the_plan(self):
        """The owner's decision of 2026-10-04 (amendment 4) makes the token-efficiency tools default installs: picked, no
        comparison group, an install command and a documented or upstream acceptance, and the install_dispatch rule that
        forbids iterating over entries kept as it was. RTK and Headroom were comparison arms until then."""
        data = self.load()
        by_name = {row["name"]: row for row in data["entries"]}
        owner = ["RTK", "Headroom", "ccusage", "context-mode", "jcodemunch-mcp", "codebase-memory-mcp", "Repomix", "TOON",
                 "MarkItDown", "Context Hub", "otel-tui", "agentsview"]
        for name in owner:
            row = by_name[name]
            with self.subTest(name=name):
                self.assertEqual((row["status"], row["default_install"], row.get("comparison_group")), ("picked", True, None))
                self.assertTrue(row["install"]["command"] and row["install"]["source"])
                self.assertTrue(row["acceptance"]["command"] and row["acceptance"]["source"])
                self.assertIn("docs/decisions/2026-10-04-token-full-stack-owner-default.md", row["evidence_refs"])
                self.assertEqual(row["layer_id"], "observation-inference" if name == "agentsview" else "token-efficiency")
        self.assertIn("[mcp]", by_name["Headroom"]["install"]["command"])
        self.assertNotIn("[all]", by_name["Headroom"]["install"]["command"])
        self.assertNotIn("cargo", by_name["RTK"]["install"]["command"])
        self.assertIn("rtk-x86_64-unknown-linux-musl.tar.gz", by_name["RTK"]["install"]["command"])
        boundary = data["boundary"]
        self.assertTrue(boundary["install_dispatch"].startswith("Do not iterate over entries."))
        for name in owner:
            self.assertIn(name, boundary["default_profile"])
        # SocratiCode stays an arm: its install comes from the plan's code-search interim, never from this profile.
        self.assertFalse(by_name["SocratiCode"]["default_install"])
        self.assertTrue(by_name["SocratiCode"]["install"]["command"])

    def assert_no_unmeasured_defaults(self, data):
        manifest = json.loads((ROOT / DEFAULTS_SOURCE).read_text())
        checked = 0
        for slot in manifest["slots"]:
            if slot.get("state") in {"split", "measurement"}:
                arms = [row for row in data["entries"] if row["layer_id"] == slot["layer_id"]
                        and (row.get("comparison_group") or row["status"] == "head-to-head-arm")]
                # A split slot added by a decision round may list no arm in this profile (agent-messaging and
                # playwright-cli do not). Then no entry of its layer may be installed by default either, because
                # that would decide the slot before its measurement returns.
                for row in arms or [row for row in data["entries"] if row["layer_id"] == slot["layer_id"]]:
                    self.assertFalse(row["default_install"], row["name"] + " in " + slot["slot_id"])
                    checked += 1
        self.assertTrue(checked, "no unresolved slot was checked")

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
        for phrase in ("last qualified release", "floor", "bootstrap installs the pin",
                       "keeps a newer existing install", "receipt", "installed version",
                       "installed and not yet qualified", "acceptance command", "passed on that host"):
            self.assertIn(phrase, rule)
        self.assertNotIn("current at install time", rule)
        # The bootstrap installs the floor, so the profile's install form names the pin, not the latest channel.
        self.assertTrue(claude["install"]["command"].endswith("bash -s " + claude["pin"]))
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
        for fragment in ("3.0.1", "2.9.13", "2.9.8", "2.7.13", "40519", "41512",
                         "adoption/platforms/linux-wsl2-new-distro.md"):
            self.assertIn(fragment, prerequisites)

    def test_accepted_cli_and_sdk_pins_do_not_assert_sdk_provisioning(self):
        data = self.load()
        rows = {row["name"]: row for row in data["entries"]}
        self.assertEqual(rows["Codex"]["pin"], "0.160.0")
        self.assertEqual(data["boundary"]["accepted_codex_cli_pin"], "0.160.0")
        self.assertEqual(data["boundary"]["accepted_python_sdk_pin"], "0.160.0")
        self.assertEqual(rows["Codex Python SDK"]["pin"], "0.160.0")
        self.assertEqual(rows["Codex TypeScript SDK"]["pin"], "0.159.3")
        for name in ("Codex TypeScript SDK", "Codex Python SDK"):
            self.assertEqual(rows[name]["provisioning_status"], "unprovisioned_source_review")
            self.assertFalse(rows[name]["default_install"])

    def paired_proof(self, data):
        return next(item for item in data["host_prerequisites"] if item["id"] == "paired-systemd-distribution-proof")

    def test_native_update_is_declared_for_both_clients_with_the_three_receipt_fields(self):
        rows = {row["name"]: row for row in self.load()["entries"]}
        for name, command in {"Claude Code": "claude install latest", "Codex": "codex update"}.items():
            with self.subTest(client=name):
                update = rows[name]["native_update"]
                self.assertEqual(update["command"], command)
                self.assertEqual(update["execution_status"], "UNRUN")
                self.assertEqual(set(update["receipt_fields"]),
                                 {"floor", "version_after_native_update", "acceptance_result_on_that_version"})
                self.assertIn(rows[name]["pin"], update["receipt_fields"]["floor"])
                self.assertIn("version actually on PATH", update["on_refusal"])
                self.assertIn("error", update["on_refusal"])
                self.assertIn("installed and not yet qualified", update["after_update"])
                self.assertIn("acceptance", update["after_update"])
        self.assertIn("Update Codex to the latest version", rows["Codex"]["native_update"]["help_observation"])
        self.assertIn("stable, latest, or specific version", rows["Claude Code"]["native_update"]["help_observation"])

    def test_negative_control_client_without_its_native_update_or_a_receipt_field_is_rejected(self):
        for name in ("Claude Code", "Codex"):
            with self.subTest(client=name, change="no native update"):
                data = self.load()
                del next(row for row in data["entries"] if row["name"] == name)["native_update"]
                result = self.fixture_cli(data)
                self.assertEqual(result.returncode, 2)
                self.assertIn("native update", result.stderr)
            with self.subTest(client=name, change="receipt field dropped"):
                data = self.load()
                row = next(row for row in data["entries"] if row["name"] == name)
                del row["native_update"]["receipt_fields"]["version_after_native_update"]
                result = self.fixture_cli(data)
                self.assertEqual(result.returncode, 2)
                self.assertIn("version after the native update", result.stderr)

    def test_paired_proof_is_declared_unrun_beside_a_rehearsal_record_that_exists(self):
        item = self.paired_proof(self.load())
        self.assertEqual(item["execution_status"], "UNRUN")
        self.assertIn("not acceptance of the real distribution", item["rehearsal"]["scope"])
        for observation in ("uid", "system state", "failed units", "user manager", "cgroup namespace"):
            self.assertIn(observation, item["requirement"])
        self.assertIn("getty mask proof", item["requirement"])
        self.assertIn("paired_isolation", item["receipt"])
        self.assertEqual(item["rehearsal"]["record"], REHEARSAL_RECORD)
        record = json.loads((ROOT / item["rehearsal"]["record"]).read_text(encoding="utf-8"))
        run = next(run for run in record["runs"] if run["id"] == "run-3")
        self.assertIn("passed", run["result"])
        self.assertIn("W5-paired", [step["step"] for step in run["steps"]])

    def test_negative_control_paired_proof_cannot_be_declared_passed_or_dropped(self):
        data = self.load()
        self.paired_proof(data)["execution_status"] = "PASSED"
        result = self.fixture_cli(data)
        self.assertEqual(result.returncode, 2)
        self.assertIn("paired proof", result.stderr)
        data = self.load()
        data["host_prerequisites"] = [item for item in data["host_prerequisites"]
                                      if item["id"] != "paired-systemd-distribution-proof"]
        result = self.fixture_cli(data)
        self.assertEqual(result.returncode, 2)
        self.assertIn("paired proof", result.stderr)

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
