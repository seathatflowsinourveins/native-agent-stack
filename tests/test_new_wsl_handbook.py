"""Public W-BOOK generator contract; these are integration checks, not host acceptance."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts import build_new_wsl_handbook as handbook


ROOT = Path(__file__).resolve().parents[1]


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

    def public_cli(self, **verdicts):
        command = [sys.executable, str(ROOT / "scripts/build_new_wsl_handbook.py"),
                   "--root", str(self.root), "--write"]
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

    def test_stage_one_stops_before_stage_two(self):
        stages = handbook.build_data(self.root)["stage_order"]
        self.assertEqual(len(stages[0]["steps"]), 7)
        self.assertEqual(len(stages[0]["first_boot_prerequisites"]), 8)
        self.assertFalse(any("F9." in step for step in stages[0]["steps"]))

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


if __name__ == "__main__":
    unittest.main()
