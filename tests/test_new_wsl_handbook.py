"""Public W-BOOK generator contract; these are integration checks, not host acceptance."""

from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_new_wsl_handbook as handbook


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_SOURCE = "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json"


class NewWslHandbookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in handbook.SOURCES:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        shutil.copytree(ROOT / handbook.PACKETS, self.root / handbook.PACKETS)
        manifest = json.loads((ROOT / DEFAULTS_SOURCE).read_text())
        for source in manifest["sources"].values():
            name = (Path(DEFAULTS_SOURCE).parent / source["file"]).as_posix()
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)

    def read(self, name):
        return json.loads((self.root / name).read_text())

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def profile(self, **changes):
        entry = {
            "name": "Claude Code", "layer_id": "native-clients",
            "owner_layer_id": "native-clients", "status": "picked",
            "repository": "https://github.com/anthropics/claude-code",
            "pin": "fixture-only-release",
            "checksum": {"algorithm": "sha256", "value": "a" * 64,
                         "kind": "artifact", "source": "https://example.org/checksums"},
            "install": {"command": "fixture-install", "source": "https://example.org/install"},
            "acceptance": {"command": "fixture-upstream-example",
                           "source": "https://example.org/example",
                           "evidence_class": "documented example; not executed"},
            "stage": 2, "position": 1, "blocking_gaps": [],
        }
        entry.update(changes)
        value = {"profile_id": "fixture-only", "source_path": handbook.PROFILE,
                 "entries": [entry]}
        self.write(handbook.PROFILE, value)
        return value

    def final_fixture(self):
        """Synthetic complete evidence, exercised through the real CLI below."""
        profile = self.profile()
        codex = deepcopy(profile["entries"][0])
        codex.update(name="Codex", repository="https://github.com/openai/codex", position=2)
        profile["entries"].append(codex)
        profile["finality"] = {"native-clients": {
            f"c{i}": {"status": "met", "source": "https://example.org/fixture-evidence"}
            for i in range(1, 6)}}
        selection_hash = handbook.digest((self.root / handbook.SELECTION).read_bytes())
        profile["comparisons"] = {"native-clients": {
            "selection_sha256": selection_hash,
            "preregistration_source": "https://example.org/fixture-preregistration"}}
        self.write(handbook.PROFILE, profile)
        packet_path = f"{handbook.PACKETS}/native-clients.json"
        packet_hash = handbook.digest((self.root / packet_path).read_bytes())
        requirement_hash = handbook.digest(self.read(packet_path)["requirement"].encode())
        paths = {}
        for family in handbook.FAMILIES:
            source = f"evidence/fixture-{family}.json"
            self.write(source, {"family": family, "selection_sha256": selection_hash,
                                "layers": [{"layer_id": "native-clients", "verdict": "confirmed",
                                            "packet_sha256": packet_hash,
                                            "requirement_sha256": requirement_hash,
                                            "release_pins": {entry["name"]: entry["pin"]
                                                             for entry in profile["entries"]},
                                            "material_gaps": []}]})
            paths[f"{family}_verdicts"] = self.root / source
        return profile, paths

    def public_cli(self, mode="--write", **verdicts):
        command = [sys.executable, str(ROOT / "scripts/build_new_wsl_handbook.py"),
                   "--root", str(self.root), mode]
        for name, path in verdicts.items():
            command += ["--" + name.replace("_", "-"), str(path)]
        return subprocess.run(command, capture_output=True, text=True)

    def package_profile(self):
        """Synthetic package facts using the verified public registry URL forms."""
        profile = self.profile(name="Codex", repository="https://github.com/openai/codex",
                               pin="0.159.3")
        prototype = deepcopy(profile["entries"][0])
        packages = [
            ("Codex", "native-clients", "npm:@openai/codex",
             "https://registry.npmjs.org/%40openai%2Fcodex/0.159.3"),
            ("Codex TypeScript SDK", "agent-sdks", "npm:@openai/codex-sdk",
             "https://registry.npmjs.org/%40openai%2Fcodex-sdk/0.159.3"),
            ("Codex Python SDK", "agent-sdks", "pypi:openai-codex",
             "https://pypi.org/pypi/openai-codex/0.159.3/json"),
        ]
        profile["entries"] = []
        for i, (name, owner, package, source) in enumerate(packages, 1):
            entry = deepcopy(prototype)
            entry.update(name=name, layer_id=owner, owner_layer_id=owner, position=i,
                         provisioning_status=f"fixture-unprovisioned-{package}")
            entry["checksum"].update(value=str(i) * 64, source=source)
            entry["install"]["command"] = f"fixture-install-{package}"
            entry["acceptance"]["command"] = f"fixture-example-{package}"
            entry["acceptance"]["execution_status"] = "UNRUN"
            if package == "npm:@openai/codex-sdk":
                entry["acceptance"] = {"command": None, "source": None}
                entry["blocking_gaps"] = ["Fixture TypeScript example remains pending."]
            profile["entries"].append(entry)
        self.write(handbook.PROFILE, profile)
        return profile, [package for _, _, package, _ in packages]

    def test_cli_separates_installable_packages_in_one_repository(self):
        profile, packages = self.package_profile()
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.read(handbook.OUTPUTS[1])
        for entry, package in zip(profile["entries"], packages):
            matches = [tool for tool in data["tools"] if tool.get("package_id") == package]
            self.assertEqual(len(matches), 1, package)
            for field in ("pin", "checksum", "install", "acceptance", "provisioning_status"):
                self.assertEqual(matches[0][field], entry[field], (package, field))
        codex = next(tool for tool in data["tools"] if tool.get("package_id") == packages[0])
        self.assertIn("workers", codex["used_by"])
        self.assertIn("Codex native workers (subagents)", codex["aliases"])
        self.assertFalse(data["new_host_acceptance_claimed"])

    def test_cli_real_profile_preserves_each_codex_package(self):
        shutil.copyfile(ROOT / handbook.PROFILE, self.root / handbook.PROFILE)
        profile = self.read(handbook.PROFILE)
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.read(handbook.OUTPUTS[1])
        expected = {"Codex": "npm:@openai/codex",
                    "Codex TypeScript SDK": "npm:@openai/codex-sdk",
                    "Codex Python SDK": "pypi:openai-codex"}
        entries = [entry for entry in profile["entries"] if entry["name"] in expected]
        self.assertEqual(len(entries), 3)
        for entry in entries:
            package = expected[entry["name"]]
            matches = [tool for tool in data["tools"] if tool.get("package_id") == package]
            self.assertEqual(len(matches), 1, package)
            for field in ("pin", "checksum", "install", "acceptance", "provisioning_status"):
                self.assertEqual(matches[0][field], entry[field], (package, field))
            self.assertTrue(set(entry["blocking_gaps"]) <= set(matches[0]["blocking_gaps"]))
        self.assertFalse(data["new_host_acceptance_claimed"])
        self.assertTrue(all(row["status"] != "final" for row in data["layers"]))
        unresolved = next(tool for tool in data["tools"]
                          if tool["name"] == "Codex SDK and codex exec/app-server")
        self.assertNotIn("package_id", unresolved)
        self.assertTrue(any("package identity" in gap for gap in unresolved["blocking_gaps"]))

    def test_cli_same_package_checksum_conflicts_still_reject(self):
        variants = [
            (1, "https://registry.npmjs.org/%40openai%2Fcodex-sdk/0.159.3"),
            (1, "https://registry.npmjs.org/@openai%2fcodex-sdk/0.159.3"),
            (2, "https://pypi.org/pypi/OpenAI_Codex/0.159.3/json"),
        ]
        for index, source in variants:
            with self.subTest(source=source):
                profile, _ = self.package_profile()
                alias = deepcopy(profile["entries"][index])
                alias["name"] += " alias"
                alias["checksum"].update(value="f" * 64, source=source)
                profile["entries"].append(alias)
                self.write(handbook.PROFILE, profile)
                result = self.public_cli()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("conflicting profile checksum", result.stderr)
                self.assertFalse(any((self.root / path).exists() for path in handbook.OUTPUTS))

    def test_cli_same_package_alias_keeps_every_blocker(self):
        profile, packages = self.package_profile()
        alias = deepcopy(profile["entries"][1])
        alias.update(name="TypeScript SDK alias", blocking_gaps=[])
        profile["entries"].append(alias)
        self.write(handbook.PROFILE, profile)
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        matches = [tool for tool in self.read(handbook.OUTPUTS[1])["tools"]
                   if tool.get("package_id") == packages[1]]
        self.assertEqual(len(matches), 1)
        self.assertIn("Fixture TypeScript example remains pending.", matches[0]["blocking_gaps"])
        self.assertIn("Codex TypeScript SDK", matches[0]["aliases"])
        self.assertIn("TypeScript SDK alias", matches[0]["aliases"])

    def test_cli_unknown_package_sources_remain_unresolved(self):
        sources = [
            "https://registry.npmjs.org.example.org/%40openai%2Fcodex-sdk/0.159.3",
            "https://registry.npmjs.org@other.example/%40openai%2Fcodex-sdk/0.159.3",
            "http://registry.npmjs.org/%40openai%2Fcodex-sdk/0.159.3",
            "https://registry.npmjs.org/%40openai%2Fcodex-sdk/0.159.3?package=other",
            "https://registry.npmjs.org/%40openai%2Fcodex-sdk/0.159.3#other",
            "https://pypi.org/pypi/openai-codex/0.159.3/download",
        ]
        for source in sources:
            with self.subTest(source=source):
                profile, _ = self.package_profile()
                unresolved = deepcopy(profile["entries"][2])
                unresolved["name"] = "Unresolved SDK package"
                unresolved["checksum"]["source"] = source
                unresolved["install"]["command"] = "python -m pip install unrelated-package==1"
                profile["entries"].append(unresolved)
                self.write(handbook.PROFILE, profile)
                result = self.public_cli()
                self.assertEqual(result.returncode, 0, result.stderr)
                tool = next(tool for tool in self.read(handbook.OUTPUTS[1])["tools"]
                            if "Unresolved SDK package" in tool["aliases"])
                self.assertNotIn("package_id", tool)
                self.assertTrue(any("package identity" in gap for gap in tool["blocking_gaps"]))

    def test_cli_unknown_package_source_does_not_inherit_single_sibling(self):
        profile, packages = self.package_profile()
        profile["entries"].pop()  # Retain only the TypeScript package in this owner/repository.
        unresolved = deepcopy(profile["entries"][1])
        unresolved["name"] = "Unresolved SDK package"
        unresolved["checksum"]["source"] = (
            "https://registry.npmjs.org.example.org/%40openai%2Fcodex-sdk/0.159.3")
        profile["entries"].append(unresolved)
        self.write(handbook.PROFILE, profile)
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.read(handbook.OUTPUTS[1])
        canonical = [tool for tool in data["tools"] if tool.get("package_id") == packages[1]]
        self.assertEqual(len(canonical), 1)
        self.assertNotIn(unresolved["name"], canonical[0]["aliases"])
        unknown = next(tool for tool in data["tools"] if unresolved["name"] in tool["aliases"])
        self.assertNotIn("package_id", unknown)
        self.assertNotEqual(canonical[0]["tool_id"], unknown["tool_id"])
        self.assertEqual(unknown["checksum"], unresolved["checksum"])
        self.assertTrue(any("package identity" in gap for gap in unknown["blocking_gaps"]))
        self.assertNotEqual(unknown["status"], "final")

    def defaults_fixture(self):
        """Synthetic records in the reviewed owner's assemble_manifest.py format."""
        layers = [{"layer_id": row["layer_id"],
                   "catalog": "foundation" if row["catalog"] == "cross" else row["catalog"],
                   "owns": [row["layer_id"] + " fixture ownership"], "uses": []}
                  for row in self.read(handbook.EDITION)["rows"]]
        slots = []
        for layer, state in [("native-clients", "definitive"), ("semantic-rag", "split"),
                             ("durable-memory", "measurement"), ("document-retrieval", "")]:
            slots.append({"catalog": "foundation", "layer_id": layer, "slot_id": layer + "-fixture",
                          "row_kind": "judged", "default": "Fixture candidate / alternative",
                          "repository": "", "installs_nothing_extra": False,
                          "definitive": state == "definitive", "state": state,
                          "label": "Synthetic source-fit decision; no execution.",
                          "claude": "converged", "gpt": "converged"})
        for catalog in ("foundation", "us-equities"):
            self.write((Path(DEFAULTS_SOURCE).parent / (catalog + ".json")).as_posix(), {
                "layers": [{"layer_id": layer["layer_id"], "slots": [
                    {"slot_id": slot["slot_id"], "default": {"name": "Fixture candidate"}}
                    for slot in slots if slot["layer_id"] == layer["layer_id"]]}
                    for layer in layers if layer["catalog"] == catalog],
                "cross_rows": [], "pinned_requirements": []})
        return {"schema_version": 1, "kind": "new-wsl-definitive-manifest",
                "date_utc": "2026-10-01", "meaning": "Fixture slot decisions only.",
                "decision_rule": "Fixture source text; this adapter makes no decisions.",
                "no_install_rule": "Fixture source text.", "not_claimed": "No host or provider acceptance.",
                "sources": {catalog: {"file": catalog + ".json", "sha256": "a" * 64}
                            for catalog in ("foundation", "us-equities")},
                "counts": {"layers": len(layers), "slots": len(slots), "definitive": 1,
                           "by_row_kind": {"judged": len(slots)}},
                "pinned_requirements": {}, "no_blind_default_today": {}, "layers": layers, "slots": slots}

    def test_defaults_manifest_actual_source_projection(self):
        source = Path(os.environ.get("NEW_WSL_DEFAULTS_FIXTURE", str(ROOT / DEFAULTS_SOURCE)))
        if not source.is_file():
            self.skipTest("owner manifest not published; supply NEW_WSL_DEFAULTS_FIXTURE for source preview")
        raw = source.read_bytes()
        manifest = json.loads(raw)
        shutil.copyfile(ROOT / handbook.PROFILE, self.root / handbook.PROFILE)
        before = handbook.build_data(self.root)
        destination = self.root / DEFAULTS_SOURCE
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.read(handbook.OUTPUTS[1])
        self.assertEqual(data["default_decisions"]["status"], "published-source")
        self.assertEqual(data["default_decisions"]["metadata"],
                         {key: value for key, value in manifest.items() if key not in {"layers", "slots"}})
        source_record = next(row for row in data["sources"] if row["path"] == DEFAULTS_SOURCE)
        self.assertEqual(source_record["sha256"], handbook.digest(raw))
        projected = []
        for layer in data["layers"]:
            expected = [slot for slot in manifest["slots"] if slot["layer_id"] == layer["layer_id"]]
            self.assertEqual([slot["record"] for slot in layer["default_slots"]], expected)
            self.assertEqual(layer["default_ownership"], next(row for row in manifest["layers"]
                                                             if row["layer_id"] == layer["layer_id"]))
            for slot in layer["default_slots"]:
                self.assertEqual(slot["state"], slot["record"].get("state") or "pending")
                projected.append(slot)
        self.assertEqual(len(projected), 74)
        self.assertEqual({state: sum(slot["state"] == state for slot in projected)
                          for state in ("definitive", "split", "measurement", "pending")},
                         {"definitive": 3, "split": 2, "measurement": 1, "pending": 68})
        self.assertEqual(data["tools"], before["tools"])
        self.assertEqual([row["status"] for row in data["layers"]],
                         [row["status"] for row in before["layers"]])
        self.assertFalse(data["new_host_acceptance_claimed"])
        markdown = (self.root / handbook.OUTPUTS[0]).read_text()
        memory = next(slot for slot in manifest["slots"] if slot["slot_id"] == "memory-owner")
        self.assertIn(memory["default"], markdown)
        self.assertIn(memory["label"], markdown)

    def test_defaults_manifest_rejects_invalid_states_layers_and_ownership(self):
        def changed_slot(data, field, value):
            data["slots"][0][field] = value
        mutations = [
            (lambda data: changed_slot(data, "state", "final"), "state"),
            (lambda data: changed_slot(data, "state", None), "state"),
            (lambda data: changed_slot(data, "layer_id", "unknown-layer"), "layer"),
            (lambda data: changed_slot(data, "catalog", "us-equities"), "catalog"),
            (lambda data: data["layers"].pop(), "layer"),
            (lambda data: data["layers"].append(deepcopy(data["layers"][0])), "duplicate layer"),
            (lambda data: data["layers"][1]["owns"].append(data["layers"][0]["owns"][0]), "ownership"),
            (lambda data: data["slots"][1].update(slot_id=data["slots"][0]["slot_id"]), "duplicate slot"),
        ]
        for mutate, message in mutations:
            with self.subTest(message=message):
                manifest = self.defaults_fixture()
                mutate(manifest)
                self.write(DEFAULTS_SOURCE, manifest)
                result = self.public_cli()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(message, result.stderr)
                self.assertFalse(any((self.root / path).exists() for path in handbook.OUTPUTS))

    def test_defaults_manifest_preview_hash_covers_complete_payload(self):
        manifest = self.defaults_fixture()
        manifest["unused_metadata"] = "Keep this field in the full source hash."
        self.write("staged-defaults.json", manifest)
        supplied = self.root / "staged-defaults.json"
        result = self.public_cli(defaults_manifest=supplied)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.read(handbook.OUTPUTS[1])
        self.assertEqual(data["default_decisions"]["status"], "supplied-preview")
        recorded = next(row for row in data["sources"] if row["path"] == DEFAULTS_SOURCE)
        self.assertEqual(recorded["sha256"], handbook.digest(supplied.read_bytes()))
        self.assertNotIn(str(supplied), json.dumps(data))
        previous = {path: (self.root / path).read_bytes() for path in handbook.OUTPUTS}
        manifest["unused_metadata"] = "private file /" + "home/" + "private/source.json"
        self.write("staged-defaults.json", manifest)
        result = self.public_cli(defaults_manifest=supplied)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)
        self.assertEqual(previous, {path: (self.root / path).read_bytes() for path in handbook.OUTPUTS})

    def test_defaults_manifest_published_path_is_confined(self):
        self.write("external-defaults.json", self.defaults_fixture())
        destination = self.root / DEFAULTS_SOURCE
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(self.root / "external-defaults.json")
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("symlinks", result.stderr)

    def test_defaults_manifest_does_not_make_source_fit_host_acceptance(self):
        before = handbook.build_data(self.root)
        self.write(DEFAULTS_SOURCE, self.defaults_fixture())
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.read(handbook.OUTPUTS[1])
        self.assertEqual(data["tools"], before["tools"])
        self.assertFalse(data["new_host_acceptance_claimed"])
        self.assertTrue(all(row["status"] != "final" for row in data["layers"]))
        slots = [slot for row in data["layers"] for slot in row["default_slots"]]
        self.assertEqual([slot["state"] for slot in slots], ["definitive", "pending", "split", "measurement"])

    def test_negative_control_unknown_slot_identifier_is_rejected(self):
        manifest = self.defaults_fixture()
        original = manifest["slots"][0]["slot_id"]
        manifest["slots"][0]["slot_id"] = "unknown-fixture-slot"
        self.write(DEFAULTS_SOURCE, manifest)
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("slot inventory", result.stderr)
        self.assertIn("unknown-fixture-slot", result.stderr)
        self.assertIn(original, result.stderr)
        self.assertFalse(any((self.root / path).exists() for path in handbook.OUTPUTS))

    def test_missing_inventory_slot_is_rejected_even_with_consistent_counts(self):
        manifest = self.defaults_fixture()
        omitted = manifest["slots"].pop()
        manifest["counts"]["slots"] -= 1
        manifest["counts"]["by_row_kind"]["judged"] -= 1
        self.write(DEFAULTS_SOURCE, manifest)
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("slot inventory", result.stderr)
        self.assertIn(omitted["slot_id"], result.stderr)

    def test_inventory_covers_roles_multiple_defaults_and_pinned_requirements(self):
        shutil.copyfile(ROOT / DEFAULTS_SOURCE, self.root / DEFAULTS_SOURCE)
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = {slot["record"]["slot_id"] for row in self.read(handbook.OUTPUTS[1])["layers"]
                    for slot in row["default_slots"]}
        self.assertEqual(rendered, {slot["slot_id"] for slot in self.read(DEFAULTS_SOURCE)["slots"]})
        self.assertTrue(any(slot.startswith("pinned/") for slot in rendered))
        self.assertTrue(any("/" in slot and not slot.startswith("pinned/") for slot in rendered))

    def test_defaults_manifest_explicit_missing_input_fails(self):
        result = self.public_cli(defaults_manifest=self.root / "missing-defaults.json")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("explicit defaults manifest input does not exist", result.stderr)

    def test_each_published_layer_appears_once(self):
        data = handbook.build_data(self.root)
        expected = [row["layer_id"] for row in self.read(handbook.EDITION)["rows"]]
        self.assertEqual([row["layer_id"] for row in data["layers"]], expected)
        self.assertEqual(len(set(expected)), 37)
        self.assertEqual(len(data["finality_gates"]), 5)

    def test_each_tool_has_one_owner_and_uses_are_references(self):
        data = handbook.build_data(self.root)
        tools = {tool["tool_id"]: tool for tool in data["tools"]}
        self.assertEqual(len(tools), len(data["tools"]))
        for tool in tools.values():
            self.assertIn(tool["owner_layer_id"], {row["layer_id"] for row in data["layers"]})
        worktrunk = [tool for tool in tools.values() if tool["repository"].endswith("/worktrunk")]
        self.assertEqual(len(worktrunk), 1)
        self.assertEqual(worktrunk[0]["owner_layer_id"], "git-github-automation")
        self.assertIn("workers", worktrunk[0]["used_by"])

    def test_missing_profile_keeps_blocking_gaps_per_pick_and_arm(self):
        data = handbook.build_data(self.root)
        for tool in data["tools"]:
            self.assertIsNone(tool["pin"])
            self.assertIsNone(tool["checksum"])
            self.assertTrue(any("pin" in gap for gap in tool["blocking_gaps"]))
            self.assertTrue(any("acceptance" in gap for gap in tool["blocking_gaps"]))
        self.assertTrue(any("profile" in gap for gap in data["blocking_gaps"]))

    def test_edition_winners_and_closure_never_become_new_recommendations(self):
        edition = self.read(handbook.EDITION)
        for row in edition["rows"]:
            row["winners"] = [{"name": "POISON-EDITION-WINNER", "pin": "999"}]
            row["closure"] = {f"c{i}": "met" for i in range(1, 6)}
        self.write(handbook.EDITION, edition)
        data = handbook.build_data(self.root)
        self.assertNotIn("POISON-EDITION-WINNER", json.dumps(data))
        trading = next(row for row in data["layers"] if row["layer_id"] == "backtesting-engine")
        self.assertEqual(trading["status"], "pending")
        self.assertEqual(trading["tools"], [])
        self.assertTrue(all(row["status"] != "final" for row in data["layers"]))

    def test_profile_fills_fields_without_claiming_execution(self):
        self.profile()
        data = handbook.build_data(self.root)
        tool = next(tool for tool in data["tools"] if tool["name"] == "Claude Code")
        self.assertEqual(tool["pin"], "fixture-only-release")
        self.assertEqual(tool["checksum"]["kind"], "artifact")
        self.assertEqual(tool["acceptance"]["command"], "fixture-upstream-example")
        self.assertEqual(tool["status"], "picked")
        self.assertFalse(data["new_host_acceptance_claimed"])

    def test_profile_cannot_reassign_a_shared_tool(self):
        self.profile(owner_layer_id="workers")
        with self.assertRaisesRegex(ValueError, "owner"):
            handbook.build_data(self.root)

    def test_source_checksum_is_not_an_install_artifact_checksum(self):
        self.profile(checksum={"algorithm": "sha256", "value": "a" * 64,
                              "kind": "source", "source": "https://example.org/source"})
        tool = next(tool for tool in handbook.build_data(self.root)["tools"]
                    if tool["name"] == "Claude Code")
        self.assertEqual(tool["checksum"]["kind"], "source")
        self.assertTrue(any("install artifact" in gap for gap in tool["blocking_gaps"]))

    def test_version_print_is_an_acceptance_gap(self):
        self.profile(acceptance={"command": "claude --version",
                                "source": "https://example.org/version"})
        tool = next(tool for tool in handbook.build_data(self.root)["tools"]
                    if tool["name"] == "Claude Code")
        self.assertTrue(any("version" in gap for gap in tool["blocking_gaps"]))

    def test_duplicate_layers_fail_closed(self):
        selection = self.read(handbook.SELECTION)
        selection["layers"].append(deepcopy(selection["layers"][0]))
        self.write(handbook.SELECTION, selection)
        with self.assertRaisesRegex(ValueError, "duplicate layer"):
            handbook.build_data(self.root)

    def test_duplicate_ownership_declarations_fail_closed(self):
        ownership = self.read(handbook.OWNERSHIP)
        ownership["layers"][1]["owns"].append(ownership["layers"][0]["owns"][0])
        self.write(handbook.OWNERSHIP, ownership)
        with self.assertRaisesRegex(ValueError, "duplicate ownership"):
            handbook.build_data(self.root)

    def test_packet_edit_breaks_preregistration_binding(self):
        path = f"{handbook.PACKETS}/native-clients.json"
        packet = self.read(path)
        packet["requirement"] += " changed after preregistration"
        self.write(path, packet)
        with self.assertRaisesRegex(ValueError, "differs from preregistration"):
            handbook.build_data(self.root)

    def test_historical_verdict_cannot_bind_another_selection(self):
        source = "evidence/fixture-verdict.json"
        self.write(source, {"family": "codex", "selection_sha256": "0" * 64, "layers": []})
        with self.assertRaisesRegex(ValueError, "current selection"):
            handbook.build_data(self.root, codex_verdicts=self.root / source)

    def test_host_paths_fail_before_writing(self):
        self.profile(install={"command": "sh /" + "home/" + "private/install.sh",
                              "source": "https://example.org/install"})
        with self.assertRaisesRegex(ValueError, "host path"):
            handbook.build_data(self.root)

    def test_negative_control_secret_install_is_rejected_before_write_and_check(self):
        self.profile()
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        previous = {path: (self.root / path).read_bytes() for path in handbook.OUTPUTS}
        secret = "sk-" + "syntheticFixtureValue" * 3
        profile = self.read(handbook.PROFILE)
        profile["entries"][0]["install"]["command"] += " --token " + secret
        self.write(handbook.PROFILE, profile)
        for mode in ("--write", "--check"):
            with self.subTest(mode=mode):
                result = self.public_cli(mode=mode)
                self.assertEqual(result.returncode, 1)
                self.assertIn("API secret", result.stderr)
                self.assertNotIn(secret, result.stdout + result.stderr)
                self.assertEqual(previous, {path: (self.root / path).read_bytes() for path in handbook.OUTPUTS})

    def test_each_rendered_output_is_scanned_before_publication(self):
        clean = handbook.render(self.root)
        secret = "ghp_" + "SyntheticFixtureValue" * 3
        for path in handbook.OUTPUTS:
            for mode in ("--write", "--check"):
                with self.subTest(path=path, mode=mode):
                    outputs = dict(clean)
                    if path.endswith(".json"):
                        data = json.loads(outputs[path])
                        data["fixture_metadata"] = secret
                        outputs[path] = json.dumps(data).encode()
                    else:
                        outputs[path] += (secret + "\n").encode()
                    # Matching on-disk bytes would otherwise let --check succeed.
                    for destination, raw in outputs.items():
                        target = self.root / destination
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(raw if mode == "--check" else b"unchanged\n")
                    previous = {name: (self.root / name).read_bytes() for name in outputs}
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with patch.object(handbook, "render", return_value=outputs), redirect_stdout(stdout), redirect_stderr(stderr):
                        code = handbook.main(["--root", str(self.root), mode])
                    self.assertEqual(code, 1)
                    self.assertIn("GitHub token", stderr.getvalue())
                    self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue())
                    self.assertEqual(previous, {name: (self.root / name).read_bytes() for name in outputs})

    def test_comparison_dependencies_and_reference_boundaries_survive(self):
        data = handbook.build_data(self.root)
        edges = {(row["before"], row["after"]) for row in data["comparison_order"]}
        self.assertEqual(edges, {("hosting-services", "isolation"),
                                 ("semantic-rag", "observation-inference")})
        self.assertIn("trading-specific", data["trading_boundary"]["text"])
        self.assertEqual(len([row for row in data["layers"] if row["layer_id"].startswith("cross:")]), 5)

    def test_unpublished_verdicts_remain_pending(self):
        data = handbook.build_data(self.root)
        for row in data["layers"]:
            self.assertEqual(set(row["family_verdicts"]), {"claude", "codex"})
            for verdict in row["family_verdicts"].values():
                self.assertEqual(verdict["status"], "pending")
                self.assertIsNone(verdict["source"])

    def test_final_cannot_be_asserted_by_a_profile_status(self):
        self.profile(status="final")
        with self.assertRaisesRegex(ValueError, "final"):
            handbook.build_data(self.root)

    def test_final_requires_both_packet_bound_verdicts_and_all_five_gates(self):
        profile, paths = self.final_fixture()
        def status(**kwargs):
            return next(row["status"] for row in handbook.build_data(self.root, **kwargs)["layers"]
                        if row["layer_id"] == "native-clients")
        self.assertEqual(status(**paths), "final")
        self.assertNotEqual(status(codex_verdicts=paths["codex_verdicts"]), "final")
        profile["finality"]["native-clients"]["c3"]["status"] = "partial"
        self.write(handbook.PROFILE, profile)
        self.assertNotEqual(status(**paths), "final")

    def test_cli_shared_entry_preserves_owner_blocker_and_prevents_final(self):
        profile, paths = self.final_fixture()
        blocker = "Owner acceptance remains unresolved in the synthetic fixture."
        profile["entries"][0]["blocking_gaps"] = [blocker]
        worker = deepcopy(profile["entries"][0])
        worker.update(name="claude-code (native subagents, worktree isolation, agent teams)",
                      layer_id="workers", blocking_gaps=[])
        profile["entries"].append(worker)
        self.write(handbook.PROFILE, profile)
        result = self.public_cli(**paths)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.read(handbook.OUTPUTS[1])
        tool = next(tool for tool in data["tools"] if tool["name"] == "Claude Code")
        self.assertIn(blocker, tool["blocking_gaps"])
        row = next(row for row in data["layers"] if row["layer_id"] == "native-clients")
        self.assertNotEqual(row["status"], "final")
        self.assertIn(blocker, (self.root / handbook.OUTPUTS[0]).read_text())

    def test_cli_rejects_root_home_install_path(self):
        command = "sh /" + "root/" + "private/install.sh"
        self.profile(install={"command": command, "source": "https://example.org/install"})
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)
        self.assertFalse(any((self.root / path).exists() for path in handbook.OUTPUTS))

    def test_cli_rejects_wsl_windows_home_install_path(self):
        command = "sh /mnt/" + "c/" + "Users/" + "private/install.sh"
        self.profile(install={"command": command, "source": "https://example.org/install"})
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)
        self.assertFalse(any((self.root / path).exists() for path in handbook.OUTPUTS))

    def test_cli_validates_unprojected_external_profile_and_verdict_fields(self):
        profile, paths = self.final_fixture()
        private_path = "/" + "root/" + "private/notes.txt"
        profile["unused_metadata"] = {"notes": [private_path]}
        self.write(handbook.PROFILE, profile)
        result = self.public_cli(**paths)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)
        del profile["unused_metadata"]
        self.write(handbook.PROFILE, profile)
        source = "evidence/fixture-codex.json"
        verdict = self.read(source)
        verdict["unused_metadata"] = {"notes": [private_path]}
        self.write(source, verdict)
        result = self.public_cli(**paths)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)

    def test_cli_allows_container_destinations_and_system_tool_paths(self):
        commands = [
            "docker run --volume cache:/" + "root/.cache image /usr/local/bin/tool",
            "docker run --rm --volume=cache:/" + "root/.cache image /usr/local/bin/tool",
            "podman run --mount type=volume,source=cache,target=/" + "root/.cache image",
            "podman run --mount=type=volume,src=cache,dst=/" + "root/.cache image",
            "/usr/local/bin/tool --config /etc/tool/config.json",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.profile(install={"command": command, "source": "https://example.org/install"})
                result = self.public_cli()
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_echo_docker_does_not_exempt_private_workdir(self):
        command = "echo docker --workdir /" + "root/WBOOK-fixture"
        self.profile(install={"command": command, "source": "https://example.org/install"})
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)
        self.assertFalse(any((self.root / path).exists() for path in handbook.OUTPUTS))

    def test_cli_later_command_cannot_inherit_container_path_exemption(self):
        command = "docker pull example.invalid/fixture-image && helper --workdir /" + "root/WBOOK-fixture"
        self.profile(install={"command": command, "source": "https://example.org/install"})
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)
        self.assertFalse(any((self.root / path).exists() for path in handbook.OUTPUTS))

    def test_cli_container_exception_does_not_cross_shell_operators(self):
        for separator in ("&&", ";", "||", "|", "\n", "&"):
            with self.subTest(separator=separator):
                command = "docker run --volume cache:/" + "root/.cache image"
                command += " " + separator + " helper --workdir /" + "root/WBOOK-fixture"
                self.profile(install={"command": command, "source": "https://example.org/install"})
                result = self.public_cli()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("host path", result.stderr)

    def test_cli_container_exception_stops_at_the_image(self):
        command = "docker run image echo --workdir /" + "root/WBOOK-fixture"
        self.profile(install={"command": command, "source": "https://example.org/install"})
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)

    def test_cli_echo_volume_text_does_not_gain_a_container_namespace(self):
        command = "echo docker run --volume cache:/" + "root/WBOOK-fixture image"
        self.profile(install={"command": command, "source": "https://example.org/install"})
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)

    def test_cli_named_volume_keeps_other_mount_fields_visible(self):
        command = "docker run --mount type=volume,source=cache,target=/" + "root/.cache"
        command += ",volume-opt=device=/" + "root/WBOOK-fixture image"
        self.profile(install={"command": command, "source": "https://example.org/install"})
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)

    def test_cli_known_multiline_reference_is_exactly_bound(self):
        layer = next(row for row in self.read(handbook.SELECTION)["layers"]
                     if row["layer_id"] == "durable-memory")
        choice = next(tool for tool in layer["selection"] if tool["name"] == "Hindsight")
        install = {"command": choice["install_command"], "source": choice["install_source"]}
        fields = {"name": "Hindsight", "layer_id": "durable-memory",
                  "owner_layer_id": "durable-memory", "repository": choice["repository"],
                  "status": "head-to-head-arm", "install": install}
        self.profile(**fields)
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        private_path = "/" + "root/WBOOK-fixture"
        install["command"] += "\necho " + private_path
        self.profile(**fields)
        changed = self.public_cli()
        self.assertEqual(changed.returncode, 1, changed.stdout)
        self.assertIn("host path", changed.stderr)
        for path in handbook.OUTPUTS:
            self.assertNotIn(private_path, (self.root / path).read_text())

    def test_cli_rejects_private_container_mount_source(self):
        command = "docker run -v /" + "root/" + "private:/workspace image"
        self.profile(install={"command": command, "source": "https://example.org/install"})
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("host path", result.stderr)

    def test_cli_changed_packet_cannot_reuse_old_verdict_after_preregistration_update(self):
        _, paths = self.final_fixture()
        original = self.public_cli(**paths)
        self.assertEqual(original.returncode, 0, original.stderr)
        self.assertEqual(next(row["status"] for row in self.read(handbook.OUTPUTS[1])["layers"]
                              if row["layer_id"] == "native-clients"), "final")
        path = f"{handbook.PACKETS}/native-clients.json"
        packet = self.read(path)
        packet["requirement"] += " New requirement after the frozen judgment."
        self.write(path, packet)
        preregistration = self.read(handbook.PREREGISTRATION)
        for row in preregistration["packets"]:
            if row["layer_id"] == "native-clients":
                row["sha256"] = handbook.digest((self.root / path).read_bytes())
        self.write(handbook.PREREGISTRATION, preregistration)
        changed = self.public_cli(**paths)
        self.assertEqual(changed.returncode, 1, changed.stdout)
        self.assertIn("current packet", changed.stderr)

    def test_cli_missing_verdict_packet_binding_remains_pending(self):
        _, paths = self.final_fixture()
        source = "evidence/fixture-codex.json"
        verdict = self.read(source)
        del verdict["layers"][0]["packet_sha256"]
        self.write(source, verdict)
        result = self.public_cli(**paths)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = next(row for row in self.read(handbook.OUTPUTS[1])["layers"]
                   if row["layer_id"] == "native-clients")
        self.assertEqual(row["family_verdicts"]["codex"]["status"], "pending")
        self.assertIn("packet", " ".join(row["family_verdicts"]["codex"]["binding_gaps"]))
        self.assertNotEqual(row["status"], "final")

    def test_cli_incorrect_requirement_or_release_binding_fails(self):
        for field, value in (("requirement_sha256", "0" * 64),
                             ("release_pins", {"Claude Code": "unjudged-release", "Codex": "fixture-only-release"})):
            with self.subTest(field=field):
                _, paths = self.final_fixture()
                source = "evidence/fixture-codex.json"
                verdict = self.read(source)
                verdict["layers"][0][field] = value
                self.write(source, verdict)
                result = self.public_cli(**paths)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("binding", result.stderr)

    def test_cli_missing_requirement_or_release_binding_remains_pending(self):
        for field in ("requirement_sha256", "release_pins"):
            with self.subTest(field=field):
                _, paths = self.final_fixture()
                source = "evidence/fixture-codex.json"
                verdict = self.read(source)
                del verdict["layers"][0][field]
                self.write(source, verdict)
                result = self.public_cli(**paths)
                self.assertEqual(result.returncode, 0, result.stderr)
                row = next(row for row in self.read(handbook.OUTPUTS[1])["layers"]
                           if row["layer_id"] == "native-clients")
                self.assertEqual(row["family_verdicts"]["codex"]["status"], "pending")
                self.assertNotEqual(row["status"], "final")

    def assert_stage_order(self, stages):
        self.assertEqual([stage["stage"] for stage in stages], [1, 2])
        self.assertEqual(len(stages[0]["steps"]), 7)
        self.assertEqual(len(stages[0]["first_boot_prerequisites"]), 8)
        self.assertFalse(any("F9." in step for step in stages[0]["first_boot_prerequisites"]),
                         "F9 belongs to stage 2")
        self.assertEqual([step.split(".", 1)[0] for step in stages[0]["steps"]],
                         [f"W{i}" for i in range(1, 8)])
        self.assertEqual([step.split(".", 1)[0] for step in stages[0]["first_boot_prerequisites"]],
                         [f"F{i}" for i in range(1, 9)])
        self.assertEqual([step.split(".", 1)[0] for step in stages[1]["after_bootstrap"]], ["F10", "F11"])

    def test_stage_one_stops_before_stage_two(self):
        self.assert_stage_order(handbook.build_data(self.root)["stage_order"])

    def test_negative_control_stage_two_cannot_enter_first_boot_prerequisites(self):
        stages = handbook.build_data(self.root)["stage_order"]
        stages[0]["first_boot_prerequisites"][-1] = "F9. Stage 2 (outside this page)"
        with self.assertRaisesRegex(AssertionError, "F9"):
            self.assert_stage_order(stages)

    def test_negative_control_first_boot_prerequisites_cannot_be_reordered(self):
        stages = handbook.build_data(self.root)["stage_order"]
        steps = stages[0]["first_boot_prerequisites"]
        steps[1], steps[2] = steps[2], steps[1]
        with self.assertRaises(AssertionError):
            self.assert_stage_order(stages)

    def test_external_profile_never_exposes_its_host_path(self):
        self.profile()
        external = self.root / "external-profile.json"
        (self.root / handbook.PROFILE).rename(external)
        data = handbook.build_data(self.root, profile_path=external)
        self.assertNotIn(str(self.root), json.dumps(data))
        self.assertIn(handbook.PROFILE, json.dumps(data["sources"]))

    def test_explicit_missing_profile_is_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            handbook.build_data(self.root, profile_path=self.root / "missing.json")

    def test_external_evidence_link_keeps_its_url(self):
        source = "https://example.org/evidence"
        self.assertEqual(handbook.link(source), f"[{source}]({source})")

    def test_check_detects_stale_output_and_regeneration_is_byte_identical(self):
        command = [sys.executable, str(ROOT / "scripts/build_new_wsl_handbook.py"),
                   "--root", str(self.root)]
        first = subprocess.run(command + ["--write"], capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = [(self.root / name).read_bytes() for name in handbook.OUTPUTS]
        second = subprocess.run(command + ["--write"], capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(before, [(self.root / name).read_bytes() for name in handbook.OUTPUTS])
        checked = subprocess.run(command + ["--check"], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        (self.root / handbook.OUTPUTS[0]).write_text("stale\n")
        failed = subprocess.run(command + ["--check"], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("stale", failed.stderr)

    def test_negative_control_check_rejects_book_after_manifest_default_changes(self):
        shutil.copyfile(ROOT / DEFAULTS_SOURCE, self.root / DEFAULTS_SOURCE)
        written = self.public_cli()
        self.assertEqual(written.returncode, 0, written.stderr)
        checked = self.public_cli(mode="--check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        previous = {path: (self.root / path).read_bytes() for path in handbook.OUTPUTS}
        manifest = self.read(DEFAULTS_SOURCE)
        manifest["slots"][0]["default"] += " Changed fixture recommendation."
        self.write(DEFAULTS_SOURCE, manifest)
        checked = self.public_cli(mode="--check")
        self.assertEqual(checked.returncode, 1)
        self.assertIn("stale generated output: docs/new-wsl-handbook.md", checked.stderr)
        self.assertEqual(previous, {path: (self.root / path).read_bytes() for path in handbook.OUTPUTS})


if __name__ == "__main__":
    unittest.main()
