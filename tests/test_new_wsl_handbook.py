"""Public W-BOOK generator contract; these are integration checks, not host acceptance."""

from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_new_wsl_handbook as handbook


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_SOURCE = "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json"
REHEARSAL_RECORD = "evidence/artifacts/new-wsl-rehearsal-20261002/runs-on-wsl-3.0.1.json"
RELEASE_SENTENCE = "adopts stable WSL 3.0.1 or later for a second systemd distribution"
RECEIPT_FIELDS = {"floor", "version_after_native_update", "acceptance_result_on_that_version"}
CLIENT_UPDATES = {"Claude Code": "claude install latest", "Codex": "codex update"}


def source_name(source):
    """The repository path of one provenance entry of the definitive manifest.

    `file` is relative to the manifest's folder and `path` to the repository root, as assemble_manifest.py writes them.
    """
    if "file" in source:
        return (Path(DEFAULTS_SOURCE).parent / source["file"]).as_posix()
    return source["path"]


def page_commands():
    """Every command line in a fenced block of the recipe page."""
    page = (ROOT / handbook.DISTRO).read_text(encoding="utf-8")
    blocks = re.findall(r"^```[a-z]*\n(.*?)^```$", page, re.MULTILINE | re.DOTALL)
    return {line.strip() for block in blocks for line in block.splitlines() if len(line.strip()) >= 15}


def table_cells(line):
    """The cells of one Markdown table row; `\\|` is a pipe inside a cell."""
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def page_block_after(page, marker):
    """The lines of the first fenced block after the marker, found without the generator's own parser."""
    match = re.search(r"```[a-z]*\n(.*?)```", page[page.index(marker):], re.DOTALL)
    return match.group(1).splitlines()


def all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from all_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_strings(child)


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
            name = source_name(source)
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)

    def read(self, name):
        return json.loads((self.root / name).read_text())

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def host_requalification_fixture(self):
        """Synthetic receipt facts for the projection contract, not host evidence."""
        decision = "docs/decisions/2026-10-05-fixture-requalification.md"
        path = self.root / decision
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Synthetic qualification decision\n\nNo host acceptance is claimed.\n")
        return {"schema_version": 1, "id": "ns2604-requalification-20261005", "kind": "historical_inventory",
                "data": {
                    "host": "NativeStack2604", "publication_date_utc": "2026-10-05",
                    "decision_record": decision,
                    "readiness": {
                        "provisional": True,
                        "formula": "(READY + BY_DESIGN) / all 80 slots in scope",
                        "baseline": {"numerator": 30, "denominator": 80, "percent": 37.5},
                        "current": {"numerator": 27, "denominator": 80, "percent": 33.75,
                                    "status": "provisional_pending_independent_review"},
                        "conditional": {"numerator": 29, "denominator": 80, "percent": 36.25,
                                        "status": "conditional_pending_four_slot_adjudication"}},
                    "disputed_slot_ids": [f"token-efficiency/{slot}" for slot in
                                          ("repo-packing", "command-output", "output-compression", "code-index")],
                    "independent_review": {"status": "pending", "scope": "New dated command-center qualification, independent review and adjudication are required."},
                    "source_class": "synthetic projection contract, not host or upstream acceptance",
                    "qualification_scope": "Synthetic lower counts exercise consistency; no independently verified labels are claimed."}}

    def test_host_requalification_absence_keeps_it_out_of_the_book(self):
        data = handbook.build_data(self.root)
        self.assertNotIn("host_requalification", data)
        self.assertNotIn(handbook.HOST_REQUALIFICATION, {source["path"] for source in data["sources"]})
        self.assertNotIn("host re-qualification", handbook.render_markdown(data).decode())

    def test_host_requalification_projects_scope_and_figures_without_promoting_acceptance(self):
        before = handbook.build_data(self.root)
        receipt = self.host_requalification_fixture()
        self.write(handbook.HOST_REQUALIFICATION, receipt)
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.read(handbook.OUTPUTS[1])
        host = data["host_requalification"]
        self.assertEqual({key: host[key] for key in receipt["data"]}, receipt["data"])
        self.assertEqual(host["source"], handbook.HOST_REQUALIFICATION)
        self.assertEqual(host["receipt_kind"], "historical_inventory")
        self.assertEqual({key: value for key, value in data.items() if key not in {"host_requalification", "sources"}},
                         {key: value for key, value in before.items() if key != "sources"})
        self.assertFalse(data["new_host_acceptance_claimed"])
        source = next(source for source in data["sources"] if source["path"] == handbook.HOST_REQUALIFICATION)
        self.assertEqual(source["sha256"], handbook.digest((self.root / handbook.HOST_REQUALIFICATION).read_bytes()))
        page = (self.root / handbook.OUTPUTS[0]).read_text()
        for text in ("Official old-bar readiness (qualified 2026-10-04): **30/80 (37.5%)**",
                     "Supplied old-bar current projection (provisional): **27/80 (33.75%)**",
                     "Old-bar conditional projection (provisional): **29/80 (36.25%)**",
                     receipt["data"]["source_class"], receipt["data"]["qualification_scope"],
                     "without an independently verified 80-slot join", "Independent review: pending",
                     "Official old-bar readiness remains the qualified 2026-10-04 baseline", receipt["data"]["decision_record"],
                     "command center's new dated qualification", "followed by independent review and adjudication"):
            self.assertIn(text, page)
        decision = next(source for source in data["sources"] if source["path"] == receipt["data"]["decision_record"])
        self.assertEqual(decision["sha256"], handbook.digest((self.root / decision["path"]).read_bytes()))
        self.assertNotIn("four-slot adjudication pending", page)
        for slot in receipt["data"]["disputed_slot_ids"]:
            self.assertIn(slot, page)
        self.assertLess(page.index("## NativeStack2604 host re-qualification"), page.index("## Stage 1 and stage 2"))
        checked = self.public_cli("--check")
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_host_requalification_null_scenarios_keep_only_available_figures_and_decision_pointer(self):
        before = handbook.build_data(self.root)
        for unavailable in (("current",), ("conditional",), ("current", "conditional")):
            with self.subTest(unavailable=unavailable):
                receipt = self.host_requalification_fixture()
                for key in unavailable:
                    receipt["data"]["readiness"][key] = None
                receipt["data"]["qualification_scope"] = (
                    "Synthetic old-bar30/80 source-review proposal asof11:44Z; "
                    "excludes custody13:02Z BY_DESIGN. No organic qualification.")
                self.write(handbook.HOST_REQUALIFICATION, receipt)
                result = self.public_cli()
                self.assertEqual(result.returncode, 0, result.stderr)
                data = self.read(handbook.OUTPUTS[1])
                host = data["host_requalification"]
                for key in unavailable:
                    self.assertIsNone(host["readiness"][key])
                page = (self.root / handbook.OUTPUTS[0]).read_text()
                section = page.split("## NativeStack2604 host re-qualification", 1)[1].split("## Stage 1 and stage 2", 1)[0]
                expected = [str(receipt["data"]["readiness"][key]["numerator"])
                            for key in ("baseline", "current", "conditional") if key not in unavailable]
                self.assertEqual(re.findall(r"\*\*(\d+)/80", section), expected)
                if unavailable == ("current", "conditional"):
                    self.assertIn("Official old-bar readiness (qualified 2026-10-04): **30/80 (37.5%)**", section)
                    self.assertEqual(re.findall(r"\*\*(\d+)/80", section), ["30"])
                    self.assertNotIn("37/80", section)
                    self.assertNotIn("32/80", section)
                self.assertIn("No aggregate established for: " + ", ".join(unavailable), section)
                self.assertIn(receipt["data"]["decision_record"], section)
                self.assertIn(receipt["data"]["qualification_scope"], section)
                self.assertIn("installed, with its checks passing", section)
                self.assertIn("organic native-arm use", section)
                self.assertIn("without prompts or harness rules naming the tool", section)
                self.assertIn("final verified E2E (S4)", section)
                self.assertIn("command center's new dated qualification", section)
                self.assertIn("public review alone does not change the official figure", section)
                self.assertNotIn("four-slot adjudication pending", section)
                self.assertFalse(data["new_host_acceptance_claimed"])
                self.assertEqual({key: value for key, value in data.items() if key not in {"host_requalification", "sources"}},
                                 {key: value for key, value in before.items() if key != "sources"})

    def test_host_requalification_requires_explicit_scenarios_and_reviewed_baseline(self):
        for missing in ("baseline", "current", "conditional"):
            with self.subTest(missing=missing):
                receipt = self.host_requalification_fixture()
                del receipt["data"]["readiness"][missing]
                self.write(handbook.HOST_REQUALIFICATION, receipt)
                with self.assertRaisesRegex(ValueError, "explicitly declared " + missing):
                    handbook.read_host_requalification(handbook.Inputs(self.root))

    def test_host_requalification_requires_a_present_public_decision_record(self):
        for value in (None, "", 42, "../outside.md", "/outside.md", "docs/README.md", "docs/decisions/missing.md"):
            with self.subTest(decision=value):
                receipt = self.host_requalification_fixture()
                receipt["data"]["decision_record"] = value
                self.write(handbook.HOST_REQUALIFICATION, receipt)
                with self.assertRaisesRegex(ValueError, "host requalification|public repository path"):
                    handbook.read_host_requalification(handbook.Inputs(self.root))

    def test_host_requalification_rejects_inconsistent_or_promoted_receipt_facts(self):
        changes = [
            ("schema_version", True), ("kind", "native_model_e2e"), ("id", "another-receipt"),
            ("data.host", "another-host"), ("data.publication_date_utc", "2026-10-06"),
            ("data.readiness.provisional", False), ("data.readiness.formula", ""),
            ("data.readiness.current.denominator", 81), ("data.readiness.current.numerator", True),
            ("data.readiness.current.numerator", -1), ("data.readiness.current.percent", 55.0),
            ("data.readiness.current.percent", True), ("data.readiness.current.status", "accepted"),
            ("data.readiness.baseline", None),
            ("data.readiness.baseline", {"numerator": 31, "denominator": 80, "percent": 38.75}),
            ("data.readiness.conditional", {"numerator": 45, "denominator": 80, "percent": 55.0,
                                          "status": "conditional_pending_four_slot_adjudication"}),
            ("data.readiness.conditional", []),
            ("data.readiness.conditional", {"numerator": 29, "denominator": 80, "percent": 36.25,
                                          "status": "accepted"}),
            ("data.disputed_slot_ids", ["token-efficiency/context-supply"] * 4),
            ("data.disputed_slot_ids", [f"token-efficiency/{slot}" for slot in
                                       ("context-supply", "command-output", "output-compression", "code-index")]),
            ("data.independent_review.status", "agreed"), ("data.independent_review.scope", ""),
            ("data.qualification_scope", ""), ("data.source_class", ""),
        ]
        for path, value in changes:
            with self.subTest(path=path, value=value):
                receipt = self.host_requalification_fixture()
                target = receipt
                keys = path.split(".")
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                self.write(handbook.HOST_REQUALIFICATION, receipt)
                with self.assertRaisesRegex(ValueError, "host requalification"):
                    handbook.read_host_requalification(handbook.Inputs(self.root))

    def test_host_requalification_change_invalidates_a_previously_generated_book(self):
        receipt = self.host_requalification_fixture()
        self.write(handbook.HOST_REQUALIFICATION, receipt)
        self.assertEqual(self.public_cli().returncode, 0)
        receipt["data"]["qualification_scope"] += " A further source gap remains open."
        self.write(handbook.HOST_REQUALIFICATION, receipt)
        stale = self.public_cli("--check")
        self.assertEqual(stale.returncode, 1)
        self.assertIn("stale generated output", stale.stderr)

    def test_host_requalification_decision_change_invalidates_a_previously_generated_book(self):
        receipt = self.host_requalification_fixture()
        self.write(handbook.HOST_REQUALIFICATION, receipt)
        self.assertEqual(self.public_cli().returncode, 0)
        decision = self.root / receipt["data"]["decision_record"]
        decision.write_text(decision.read_text() + "\nA further adjudication remains required.\n")
        stale = self.public_cli("--check")
        self.assertEqual(stale.returncode, 1)
        self.assertIn("stale generated output", stale.stderr)

    def test_host_requalification_rejects_private_omitted_metadata_before_publication(self):
        receipt = self.host_requalification_fixture()
        receipt["private_omitted_metadata"] = "/home/" + "private-user/coordination/source.json"
        self.write(handbook.HOST_REQUALIFICATION, receipt)
        result = self.public_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("host path", result.stderr)
        self.assertTrue(all(not (self.root / output).exists() for output in handbook.OUTPUTS))

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

    def test_a_re_pin_leaves_the_adoption_manifest_digest_unchanged(self):
        """The handbook is a new-machine file: hashing the release pointer would make every re-pin stale it."""
        manifest = {"schema_version": 1, "updated_at": "2026-10-04",
                    "source": {"repository": "example/repo", "release_tag": "v1", "release_commit": "a" * 40},
                    "profiles": {"workstation": ["step"]}}
        digests = []
        for change in (None, "repin", "content"):
            data = deepcopy(manifest)
            if change == "repin":
                data["updated_at"] = "2026-10-05"
                data["source"].update(release_tag="v2", release_commit="b" * 40)
            elif change == "content":
                data["profiles"]["workstation"].append("new step")
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "adoption").mkdir()
                (root / handbook.ADOPTION).write_text(json.dumps(data, indent=2) + "\n")
                inputs = handbook.Inputs(root)
                inputs.read(handbook.ADOPTION)
                record = inputs.sources[handbook.ADOPTION]
                self.assertEqual(record["excludes"], list(handbook.ADOPTION_POINTER_FIELDS))
                digests.append(record["sha256"])
        self.assertEqual(digests[0], digests[1])
        self.assertNotEqual(digests[0], digests[2])

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

    def test_owner_browser_replacement_has_one_pick_and_a_complete_checksum(self):
        self.real_tree()
        data = handbook.build_data(self.root)
        self.assertFalse(any(tool["name"] == "Playwright CLI" and tool["status"] == "picked"
                             for tool in data["tools"]))
        chrome, = [tool for tool in data["tools"] if tool["name"] == "Chrome DevTools MCP"]
        self.assertEqual(chrome["status"], "picked")
        self.assertEqual(chrome["checksum"]["algorithm"], "sha256")
        self.assertRegex(chrome["checksum"]["value"], r"^[0-9a-f]{64}$")
        self.assertTrue(chrome["checksum"]["integrity"].startswith("sha512-"))
        self.assertFalse(any("checksum" in gap.lower() for gap in chrome["blocking_gaps"]))

        # A profile without the explicit historical-name binding must still
        # surface the unfulfilled old pick; this is not a global name filter.
        profile = self.read(handbook.PROFILE)
        entry, = [entry for entry in profile["entries"] if entry["name"] == "Chrome DevTools MCP"]
        entry.pop("source_selection_name")
        self.write(handbook.PROFILE, profile)
        control = handbook.build_data(self.root)
        self.assertTrue(any(tool["name"] == "Playwright CLI" and tool["status"] == "picked"
                            and tool["blocking_gaps"] for tool in control["tools"]))

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

    def fixture_slot(self, layer, state):
        """One synthetic row in the producer's shape: a split or an unreturned measurement installs nothing."""
        waiting = state in ("split", "measurement")
        return {"catalog": "foundation", "layer_id": layer, "slot_id": layer + "-fixture",
                "row_kind": "judged",
                "default": "Not installed until the fixture measurement returns" if waiting
                else "Fixture candidate / alternative",
                "repository": "", "installs_nothing_extra": waiting,
                "definitive": state == "definitive", "state": state,
                "measurement": {"returned": False, "receipts": []} if waiting else None,
                "label": "Synthetic source-fit decision; no execution.",
                "coincides_with_lane_record": None, "claude": "converged", "gpt": "converged",
                "job": layer + " fixture job",
                "resolution": {"outcome": {"definitive": "final", "split": "split"}.get(state, "kept"),
                               "reason": "Synthetic fixture reason for " + layer + "."}}

    def fixture_counts(self, manifest):
        """The counts the producer writes, computed again from the fixture's own rows."""
        kinds, states = {}, {}
        for row in manifest["slots"]:
            kinds[row["row_kind"]] = kinds.get(row["row_kind"], 0) + 1
            states[row["state"] or "open"] = states.get(row["state"] or "open", 0) + 1
        return {"layers": len(manifest["layers"]), "slots": len(manifest["slots"]),
                "definitive": sum(row["definitive"] for row in manifest["slots"]),
                "by_row_kind": kinds, "by_state": states,
                "installed": sum(bool(row["default"]) and not row["installs_nothing_extra"]
                                 for row in manifest["slots"])}

    def defaults_fixture(self):
        """Synthetic records in the reviewed owner's assemble_manifest.py format."""
        layers = [{"layer_id": row["layer_id"],
                   "catalog": "foundation" if row["catalog"] == "cross" else row["catalog"],
                   "owns": [row["layer_id"] + " fixture ownership"], "uses": []}
                  for row in self.read(handbook.EDITION)["rows"]]
        slots = [self.fixture_slot(layer, state) for layer, state in
                 [("native-clients", "definitive"), ("semantic-rag", "split"),
                  ("durable-memory", "measurement"), ("document-retrieval", "")]]
        sources = {}
        for catalog in ("foundation", "us-equities"):
            name = (Path(DEFAULTS_SOURCE).parent / (catalog + ".json")).as_posix()
            self.write(name, {
                "layers": [{"layer_id": layer["layer_id"], "slots": [
                    {"slot_id": slot["slot_id"], "default": {"name": "Fixture candidate"}}
                    for slot in slots if slot["layer_id"] == layer["layer_id"]]}
                    for layer in layers if layer["catalog"] == catalog],
                "cross_rows": [], "pinned_requirements": []})
            sources[catalog] = {"file": catalog + ".json", "sha256": handbook.digest((self.root / name).read_bytes())}
        manifest = {"schema_version": 1, "kind": "new-wsl-definitive-manifest",
                    "date_utc": "2026-10-01", "meaning": "Fixture slot decisions only.",
                    "decision_rule": "Fixture source text; this adapter makes no decisions.",
                    "no_install_rule": "Fixture source text.", "not_claimed": "No host or provider acceptance.",
                    "sources": sources, "pinned_requirements": {}, "no_blind_default_today": {},
                    "layers": layers, "slots": slots}
        manifest["counts"] = self.fixture_counts(manifest)
        return manifest

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
                self.assertEqual(slot["state"], slot["record"].get("state") or "open")
                projected.append(slot)
        # Every expectation comes from the manifest itself, never from a typed number.
        self.assertEqual(len(projected), len(manifest["slots"]))
        shown = {state: sum(slot["state"] == state for slot in projected)
                 for state in ("definitive", "resolved", "split", "measurement", "open")}
        self.assertEqual({state: count for state, count in shown.items() if count}, manifest["counts"]["by_state"])
        self.assertEqual(data["default_decisions"]["inventory"]["by_state"], manifest["counts"]["by_state"])
        # The published owner amendment replaces the historical browser pick.
        # All other tools retain exactly their previous inventory and metadata.
        old_tools = {tool["tool_id"]: tool for tool in before["tools"]}
        new_tools = {tool["tool_id"]: tool for tool in data["tools"]}
        removed, = old_tools.keys() - new_tools.keys()
        self.assertEqual(old_tools[removed]["name"], "Playwright CLI")
        self.assertFalse(new_tools.keys() - old_tools.keys())
        for identity, tool in new_tools.items():
            self.assertEqual(tool, old_tools[identity], identity)
        chrome, = [tool for tool in data["tools"] if tool["name"] == "Chrome DevTools MCP"]
        browser = next(slot for slot in manifest["slots"] if slot["slot_id"] == "playwright-cli")
        self.assertIn(chrome["name"], browser["default"])
        self.assertEqual(browser["resolution"]["outcome"], "owner_default")
        self.assertEqual([row["status"] for row in data["layers"]],
                         [row["status"] for row in before["layers"]])
        self.assertFalse(data["new_host_acceptance_claimed"])
        markdown = (self.root / handbook.OUTPUTS[0]).read_text()
        memory = next(slot for slot in manifest["slots"] if slot["slot_id"] == "memory-owner")
        self.assertIn(memory["default"], markdown)
        self.assertIn(memory["label"], markdown)

    def test_code_navigation_current_defaults_replace_the_historical_client_split(self):
        data = handbook.build_data(ROOT)
        layer = next(row for row in data["layers"] if row["layer_id"] == "code-navigation")
        self.assertIn("Serena (symbol navigation and references for both clients)", layer["owns"])
        self.assertFalse(any("LSP" in owner or "Codex sessions" in owner for owner in layer["owns"]))
        self.assertEqual(layer["ownership_source"], handbook.DEFAULTS_MANIFEST)
        slots = {slot["record"]["slot_id"]: slot for slot in layer["default_slots"]}
        self.assertTrue(slots["serena"]["installed"])
        self.assertFalse(slots["claude-plugins-official-code-intelligence-lsp-pl"]["installed"])
        markdown = handbook.render_markdown(data).decode()
        navigation = markdown.split("## code-navigation:", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("Serena (Codex sessions)", navigation)
        lsp = next(line for line in navigation.splitlines()
                   if "| claude-plugins-official-code-intelligence-lsp-pl |" in line)
        self.assertIn("not installed:", lsp)
        self.assertIn("Historical recommendation packet tools", navigation)
        self.assertFalse(data["new_host_acceptance_claimed"])

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
        self.assertEqual([slot["state"] for slot in slots], ["definitive", "open", "split", "measurement"])

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
        manifest["counts"] = self.fixture_counts(manifest)
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
        planted = "sk-" + "syntheticFixtureValue" * 3
        profile = self.read(handbook.PROFILE)
        profile["entries"][0]["install"]["command"] += " --token " + planted
        self.write(handbook.PROFILE, profile)
        for mode in ("--write", "--check"):
            with self.subTest(mode=mode):
                result = self.public_cli(mode=mode)
                self.assertEqual(result.returncode, 1)
                self.assertIn("API secret", result.stderr)
                self.assertNotIn(planted, result.stdout + result.stderr)
                self.assertEqual(previous, {path: (self.root / path).read_bytes() for path in handbook.OUTPUTS})

    def test_each_rendered_output_is_scanned_before_publication(self):
        clean = handbook.render(self.root)
        planted = "ghp_" + "SyntheticFixtureValue" * 3
        for path in handbook.OUTPUTS:
            for mode in ("--write", "--check"):
                with self.subTest(path=path, mode=mode):
                    outputs = dict(clean)
                    if path.endswith(".json"):
                        data = json.loads(outputs[path])
                        data["fixture_metadata"] = planted
                        outputs[path] = json.dumps(data).encode()
                    else:
                        outputs[path] += (planted + "\n").encode()
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
                    self.assertNotIn(planted, stdout.getvalue() + stderr.getvalue())
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

    # Repair for the merged definitive manifest and the platform review of 2026-10-02.

    def committed(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def real_tree(self):
        """The real manifest and profile beside the copied sources, so that the real generator runs on real inputs."""
        for name in (DEFAULTS_SOURCE, handbook.PROFILE):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)

    def generated(self):
        self.real_tree()
        result = self.public_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.read(handbook.OUTPUTS[1]), (self.root / handbook.OUTPUTS[0]).read_text(encoding="utf-8")

    def slot_lines(self, markdown):
        """Each slot table row of the handbook by slot id: a slot row has ten cells and a tool row has six.

        The header, the separator and the placeholder of a layer with no slot in the manifest are not slots.
        """
        rows = {}
        for line in markdown.splitlines():
            cells = table_cells(line) if line.startswith("| ") else []
            if len(cells) == 10 and cells[0] not in ("Slot", "---", "pending slot publication"):
                self.assertNotIn(cells[0], rows, "slot shown twice")
                rows[cells[0]] = cells
        return rows

    def test_inventory_holds_all_104_manifest_rows_the_ten_added_the_six_consensus_and_the_fourteen_owner_ones(self):
        # The sixth consensus row, statusline, comes from the layer consensus's wave-2 batch (2026-10-03), and the ten owner
        # rows from wave 3 and four round-2 rows from wave 5 (amendment 4).
        data, markdown = self.generated()
        manifest = self.read(DEFAULTS_SOURCE)
        self.assertEqual(len(manifest["slots"]), 104)
        self.assertEqual(sum(row["row_kind"] == "added" for row in manifest["slots"]), 10)
        self.assertEqual(sum(row["row_kind"] == "consensus" for row in manifest["slots"]), 6)
        self.assertEqual(sum(row["row_kind"] == "owner_decision" for row in manifest["slots"]), 14)
        rows = {slot["record"]["slot_id"]: (layer["layer_id"], slot)
                for layer in data["layers"] for slot in layer.get("default_slots", [])}
        self.assertEqual(len(rows), 104)
        lines = self.slot_lines(markdown)
        self.assertEqual(set(lines), set(rows))
        for row in manifest["slots"]:
            layer_id, slot = rows[row["slot_id"]]
            cells = lines[row["slot_id"]]
            with self.subTest(slot=row["slot_id"]):
                state = row["state"] or "open"
                self.assertEqual(layer_id, row["layer_id"])
                self.assertEqual(slot["record"], row)
                self.assertEqual([slot["state"], cells[1]], [state, state])
                self.assertEqual(cells[2], row["job"])
                self.assertIn(row["default"] or "none", cells[3])
                self.assertEqual(cells[5], row["repository"] or "none")
                self.assertEqual(cells[6], row["resolution"]["outcome"])
                self.assertIn(f"{row['catalog']} / {row['layer_id']} / {row['row_kind']}", cells[9])
        self.assertEqual(sum(slot["record"]["row_kind"] == "added" for _, slot in rows.values()), 10)
        # Counts come from the rows and agree with the manifest's own.
        inventory = data["default_decisions"]["inventory"]
        self.assertEqual({key: inventory[key] for key in manifest["counts"]}, manifest["counts"])
        self.assertEqual(inventory["installed"] + inventory["not_installed"], 104)
        self.assertIn("The manifest holds 104 slots in 37 layers.", markdown)
        self.assertIn("added 10", markdown)
        self.assertIn("consensus 6", markdown)
        self.assertIn("owner_decision 14", markdown)
        # The interim installs of amendment 3 are counted apart from the decided installs, as the producer counts them.
        self.assertEqual(inventory["interim"], sum(1 for row in manifest["slots"] if row.get("interim")))
        self.assertIn(f"{inventory['interim']} of the slots that install nothing by their decided default carry an "
                      "interim install", markdown)

    def test_consensus_rows_and_amendments_come_from_the_manifest_and_its_consensus_record(self):
        """A consensus row is shown as the manifest gives it; an amendment is listed under its layer and changes no cell."""
        data, markdown = self.generated()
        manifest = self.read(DEFAULTS_SOURCE)
        consensus = self.read(manifest["sources"]["consensus"]["path"])
        lines = self.slot_lines(markdown)
        wave2 = consensus.get("wave2") or {}
        added = {row["slot_id"]: row for row in consensus["add_rows"] + wave2.get("add_rows", [])}
        self.assertEqual({row["slot_id"] for row in manifest["slots"] if row["row_kind"] == "consensus"}, set(added))
        self.assertIn("statusline", added)          # the wave-2 batch's row (2026-10-03)
        for slot_id, row in added.items():
            with self.subTest(slot=slot_id):
                cells = lines[slot_id]
                self.assertEqual(cells[1], row["state"])
                self.assertEqual(cells[6], row["resolution"]["outcome"])
                self.assertEqual(cells[7], row["label"])
                self.assertIn(f"{row['catalog']} / {row['layer_id']} / consensus", cells[9])
                self.assertFalse(row["definitive"])
        amendments = [(row["slot_id"], item) for row in manifest["slots"] for item in row.get("amendments", [])]
        self.assertEqual(len(amendments), len(consensus["amend_rows"]) + len(wave2.get("amend_rows", [])))
        self.assertEqual(data["default_decisions"]["inventory"]["amendments"], len(amendments))
        self.assertIn(f"Rows of kind consensus: {len(added)}; amendments: {len(amendments)}.", markdown)
        for slot_id, item in amendments:
            with self.subTest(amended=slot_id):
                self.assertIn(f"- Amendment to `{slot_id}` ({item['date_utc']}; {item['by']}): {item['decision']}.", markdown)
        # The record a consensus row came from is one of the manifest's hashed sources.
        recorded = next(row for row in data["sources"] if row["path"] == manifest["sources"]["consensus"]["path"])
        self.assertEqual(recorded["sha256"], manifest["sources"]["consensus"]["sha256"])

    def test_a_consensus_row_must_match_the_consensus_record_and_is_never_definitive(self):
        self.real_tree()
        original = self.read(DEFAULTS_SOURCE)

        def recount(manifest):
            manifest["counts"] = self.fixture_counts(manifest)

        def relabel(manifest):
            # A row that no round and no consensus record names cannot call itself a consensus row.
            next(row for row in manifest["slots"] if row["slot_id"] == "codex")["row_kind"] = "consensus"
            recount(manifest)

        def unlabel(manifest):
            next(row for row in manifest["slots"] if row["slot_id"] == "skill-discovery")["row_kind"] = "added"
            recount(manifest)

        def round_outcome(manifest):
            next(row for row in manifest["slots"] if row["slot_id"] == "skill-discovery")["resolution"]["outcome"] = "final"

        def definitive(manifest):
            # The flag and the state agree, as the producer's flag check requires, and the outcome is the record's own:
            # only the rule that a consensus row is never definitive refuses it.
            next(row for row in manifest["slots"] if row["slot_id"] == "skill-discovery").update(definitive=True,
                                                                                                state="definitive")
            recount(manifest)

        def bare_amendment(manifest):
            del next(row for row in manifest["slots"] if row["slot_id"] == "codex")["amendments"][0]["decision"]

        for mutate, message in ((relabel, "consensus row differs from the layer-consensus record: codex"),
                                (unlabel, "consensus row differs from the layer-consensus record: skill-discovery"),
                                (round_outcome, "is never definitive and carries no outcome of the rounds: skill-discovery"),
                                (definitive, "is never definitive and carries no outcome of the rounds: skill-discovery"),
                                (bare_amendment, "amendment needs its date, its author and its decision: codex")):
            with self.subTest(mutation=mutate.__name__, message=message):
                manifest = deepcopy(original)
                mutate(manifest)
                self.write(DEFAULTS_SOURCE, manifest)
                result = self.public_cli()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(message, result.stderr)

    def test_owner_rows_and_owner_defaults_come_from_the_owner_batch_and_list_what_they_replace(self):
        """Amendment 4 (wave 3, 2026-10-04): a row the owner added is shown as the batch gives it, an owner default with the
        owner's outcome, and what each owner decision replaced is listed under its layer's table."""
        data, markdown = self.generated()
        manifest = self.read(DEFAULTS_SOURCE)
        consensus = self.read(manifest["sources"]["consensus"]["path"])
        lines = self.slot_lines(markdown)
        added = {row["slot_id"]: row for batch in (consensus["wave3"], consensus["wave5"])
                 for row in batch["add_rows"]}
        self.assertEqual({row["slot_id"] for row in manifest["slots"] if row["row_kind"] == "owner_decision"}, set(added))
        self.assertEqual(len(added), 14)
        for slot_id, row in added.items():
            with self.subTest(owner_row=slot_id):
                cells = lines[slot_id]
                self.assertEqual((cells[1], cells[4], cells[6], cells[7]),
                                 (row["state"], "installed", "added_by_owner_decision", row["label"]))
                self.assertIn(f"{row['catalog']} / {row['layer_id']} / owner_decision", cells[9])
        overturned = [row for row in manifest["slots"] if row.get("overturned")]
        self.assertEqual(sorted(row["slot_id"] for row in overturned),
                         ["agent-messaging", "ccusage", "code-search", "context-supply", "playwright-cli",
                          "promptfoo", "session-analytics"])
        for row in overturned:
            item = row["overturned"]["amendment"]
            with self.subTest(owner_amendment=row["slot_id"]):
                self.assertIn(f"- Owner decision on `{row['slot_id']}` ({item['date_utc']}; {item['by']}): {item['decision']}.",
                              markdown)
                if row["overturned"].get("fields"):
                    self.assertEqual(lines[row["slot_id"]][6], "owner_default")
                    self.assertEqual(lines[row["slot_id"]][4], "installed")
        inventory = data["default_decisions"]["inventory"]
        self.assertEqual(inventory["owner_amendments"], len(overturned))
        self.assertIn(f"Rows of kind owner_decision: {len(added)}; owner amendments: {len(overturned)}.", markdown)

    def test_an_owner_row_or_owner_default_must_match_the_owner_batch(self):
        """Negative controls: a row of the owner batch relabelled, a decided row that calls itself an owner row, an owner row
        with an outcome of the rounds or definitive, and an owner default without the outcome it replaced are refused."""
        self.real_tree()
        original = self.read(DEFAULTS_SOURCE)

        def slot(manifest, slot_id):
            return next(row for row in manifest["slots"] if row["slot_id"] == slot_id)

        def relabel_owner_row(manifest):
            slot(manifest, "command-output")["row_kind"] = "consensus"

        def claim_owner_row(manifest):
            slot(manifest, "codex")["row_kind"] = "owner_decision"

        def round_outcome(manifest):
            slot(manifest, "command-output")["resolution"]["outcome"] = "final"

        def definitive(manifest):
            slot(manifest, "command-output").update(definitive=True, state="definitive")

        def lost_replaced_outcome(manifest):
            slot(manifest, "ccusage")["overturned"]["fields"]["resolution"]["outcome"] = "unknown"

        def bare_owner_amendment(manifest):
            del slot(manifest, "ccusage")["overturned"]["amendment"]["decision"]

        for mutate, message in (
                (relabel_owner_row, "consensus row differs from the layer-consensus record: command-output"),
                (claim_owner_row, "consensus row differs from the layer-consensus record: codex"),
                (round_outcome, "owner row is never definitive and carries the owner's outcome: command-output"),
                (definitive, "owner row is never definitive and carries the owner's outcome: command-output"),
                (lost_replaced_outcome, "owner default needs the owner's outcome and the rounds' outcome it replaced: ccusage"),
                (bare_owner_amendment, "owner amendment needs its date, its author and its decision: ccusage")):
            with self.subTest(mutation=mutate.__name__):
                manifest = deepcopy(original)
                mutate(manifest)
                self.write(DEFAULTS_SOURCE, manifest)
                result = self.public_cli()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(message, result.stderr)

    def test_a_split_row_is_shown_as_not_installed_with_the_manifests_reason(self):
        """A measurement row whose measurement returned installs its settled default, as the manifest counts it."""
        data, markdown = self.generated()
        lines = self.slot_lines(markdown)
        rows = [slot for layer in data["layers"] for slot in layer["default_slots"]]

        def waits(record):
            return (record["state"] == "split" or record["resolution"]["outcome"] == "not_installed"
                    or (record["measurement"] is not None and not record["measurement"]["returned"]))
        waiting = [slot for slot in rows if waits(slot["record"])]
        self.assertTrue(any(slot["state"] == "split" for slot in waiting))
        for slot in waiting:
            record = slot["record"]
            with self.subTest(slot=record["slot_id"]):
                reason = record["resolution"]["reason"]
                self.assertFalse(slot["installed"])
                self.assertEqual(slot["not_installed_reason"], reason)
                interim = record.get("interim")
                # A waiting row that carries an interim install (amendment 3) shows it beside its decided default's reason;
                # an interim of several repositories (amendment 4 widened code-search's) names them all, not as one link.
                if interim:
                    repositories = [part.strip() for part in interim["repository"].split(";")]
                    named = (f"[{interim['default']}]({repositories[0]})" if len(repositories) == 1
                             else f"{interim['default']} ({', '.join(repositories)})")
                expected = ("not installed: " + reason if not interim else
                            f"interim install ({interim['date_utc']}, amendment 3): {named}"
                            f"; its decided default is not installed: {reason}")
                self.assertEqual(lines[record["slot_id"]][4], expected)
        self.assertEqual(sorted(slot["record"]["slot_id"] for slot in waiting if slot["record"].get("interim")),
                         ["code-search", "memory-owner"])
        messaging = next(slot for slot in rows if slot["record"]["slot_id"] == "agent-messaging")
        consensus = self.read("evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json")
        owner = next(e["owner_default"] for e in consensus["wave5"]["amend_rows"]
                     if e["slot_id"] == "agent-messaging")
        self.assertEqual(messaging["state"], "resolved")
        self.assertEqual(messaging["record"]["default"], owner["default"])
        self.assertEqual(lines["agent-messaging"][4], "installed")
        self.assertEqual(messaging["record"]["overturned"]["fields"]["state"], "split")
        self.assertTrue(messaging["record"]["overturned"]["fields"]["resolution"]["reason"].startswith(
            "native facilities do not cover"))
        returned = [slot for slot in rows
                    if slot["record"]["measurement"] and slot["record"]["measurement"]["returned"]]
        self.assertTrue(returned)
        for slot in returned:
            record = slot["record"]
            installs = bool(record["default"]) and not record["installs_nothing_extra"]
            self.assertEqual(slot["installed"], installs)
            self.assertEqual(lines[record["slot_id"]][4],
                             "installed" if installs else "not installed: " + record["resolution"]["reason"])

    def test_negative_control_a_split_row_that_installs_something_is_rejected(self):
        self.real_tree()
        manifest = self.read(DEFAULTS_SOURCE)
        row = next(row for row in manifest["slots"] if row["state"] == "split")
        row.update(installs_nothing_extra=False, default="A tool", repository="https://example.org/tool")
        self.write(DEFAULTS_SOURCE, manifest)
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("installs something while it waits", result.stderr)
        self.assertIn(row["slot_id"], result.stderr)

    def test_a_manifest_source_that_differs_from_its_declared_hash_is_rejected(self):
        for name, source in json.loads((ROOT / DEFAULTS_SOURCE).read_text())["sources"].items():
            with self.subTest(source=name):
                self.real_tree()
                path = self.root / source_name(source)
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                result = self.public_cli()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(f"source {name} differs from its declared SHA-256", result.stderr)
                path.write_bytes(original)

    def test_the_generator_refuses_a_recipe_page_without_the_paired_record(self):
        self.real_tree()
        page = self.root / handbook.DISTRO
        text = page.read_text(encoding="utf-8")
        marker = "Then record the same five observations"
        self.assertEqual(text.count(marker), 1)
        page.write_text(text.replace(marker, "Then record the observations"), encoding="utf-8")
        result = self.public_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("W5 has no paired record", result.stderr)

    def test_no_recipe_command_is_typed_into_the_generator_or_the_profile(self):
        commands = page_commands()
        self.assertIn("readlink /proc/self/ns/cgroup", commands)
        generator = self.committed("scripts/build_new_wsl_handbook.py")
        profile_data = json.loads(self.committed(handbook.PROFILE))
        promptfoo = next(row for row in profile_data["entries"] if row["name"] == "promptfoo")
        # A tool recipe may point at its canonical plan row; it does not duplicate F9's stage block.
        plan_path = "evidence/artifacts/new-wsl-install-plan-20261002"
        self.assertTrue(promptfoo["default_install"])
        self.assertEqual(promptfoo["install"]["command"], f"bash {plan_path}/install.sh --only promptfoo")
        self.assertEqual(promptfoo["install"]["source"], f"{plan_path}/install-plan.json")
        promptfoo["install"]["command"] = ""
        profile = "\n".join(all_strings(profile_data))
        profile += "\n" + self.committed("adoption/new-wsl-profile.md")
        for command in sorted(commands):
            with self.subTest(command=command):
                self.assertNotIn(command, generator)
                self.assertNotIn(command, profile)
        # Stage 2 once carried its commands as typed text; they are F9's block now, and the steps only point at F9.
        for typed in ("bootstrap-linux.sh", "codex login", "--configure-full-profile"):
            self.assertNotIn(typed, generator)
        self.assertEqual(handbook.build_data(self.root)["stage_order"][1]["commands"],
                         page_block_after(self.committed(handbook.DISTRO), "### F9."))

    def assert_release_is_a_target(self, label, text):
        """The release is a selected target for a second systemd distribution, never a universal minimum."""
        flat = " ".join(text.split())
        self.assertIn(RELEASE_SENTENCE, flat, label)
        for sentence in re.split(r"(?<=[.!?])\s+", flat):
            if "3.0.1" in sentence and "second systemd distribution" in sentence:
                self.assertNotRegex(sentence, r"(?i)\b(?:minimum|universal|requires?|required)\b",
                                    label + ": " + sentence)

    def test_wsl_release_is_the_adopted_target_and_no_sentence_calls_it_a_universal_minimum(self):
        profile = json.loads(self.committed(handbook.PROFILE))
        data = json.loads(self.committed(handbook.OUTPUTS[1]))
        texts = {"profile JSON": " ".join(all_strings(profile["host_prerequisites"])),
                 "profile page": self.committed("adoption/new-wsl-profile.md"),
                 "handbook JSON": " ".join(all_strings(data["profile"]["host_prerequisites"])),
                 "handbook": self.committed(handbook.OUTPUTS[0])}
        for label, text in texts.items():
            with self.subTest(text=label):
                self.assert_release_is_a_target(label, text)
        item = next(item for item in profile["host_prerequisites"] if item["id"] == "wsl-release-target")
        self.assertIn("not adopted", item["not_adopted"])
        for version in ("2.9.8", "2.9.13", "40519", "41512"):
            self.assertIn(version, item["not_adopted"])
        self.assertIn("lower install-only minimum", item["single_distribution"])
        self.assertIn("2.4.10", item["single_distribution"])
        # The observations are stated, and apart from the policy.
        policy = " ".join([item["requirement"], item["not_adopted"], item["single_distribution"]])
        observations = " ".join(item["observations"])
        self.assertNotIn("2.7.13", policy)
        for fragment in ("2.7.13", "shared cgroups", "3.0.1.0", "2026-10-02"):
            self.assertIn(fragment, observations)
        # Nothing here restates a version that the recipe page's host-wide rules do not have.
        page = self.committed(handbook.DISTRO)
        rules = page[page.index("## Host-wide rules"):page.index("## Rehearsal first")]
        for version in set(re.findall(r"\b\d+\.\d+\.\d+(?:\.\d+)?\b", policy + " " + observations)):
            self.assertIn(version, rules, version)

    def test_paired_proof_is_named_with_its_real_status_and_the_rehearsal_record(self):
        profile = json.loads(self.committed(handbook.PROFILE))
        data = json.loads(self.committed(handbook.OUTPUTS[1]))
        markdown = self.committed(handbook.OUTPUTS[0])
        item = next(item for item in profile["host_prerequisites"]
                    if item["id"] == "paired-systemd-distribution-proof")
        self.assertEqual(item["execution_status"], "UNRUN")
        self.assertEqual(item["rehearsal"]["record"], REHEARSAL_RECORD)
        self.assertTrue((ROOT / REHEARSAL_RECORD).is_file())
        self.assertIn(item, data["profile"]["host_prerequisites"])
        self.assertNotRegex(" ".join(all_strings(item)), r"(?i)real distribution (?:has passed|passed|passes|is accepted)")
        for observation in ("uid", "system state", "failed units", "user manager", "cgroup namespace"):
            self.assertIn(observation, item["requirement"])
        self.assertIn("getty mask proof", item["requirement"])
        self.assertIn("A version check or one healthy user bus does not satisfy it.", item["requirement"])
        self.assertIn("Status for the real distribution: **UNRUN**.", markdown)
        self.assertIn(REHEARSAL_RECORD, markdown)
        self.assertIn("run 3 of 2026-10-02 passed it", markdown)
        self.assertIn("A rehearsal is not acceptance of the real distribution.", markdown)
        # The five observations, the pass rule and the getty mask proof are the recipe page's own text.
        page = self.committed(handbook.DISTRO)
        flat_page = " ".join(page.split())
        paired = data["paired_proof"]
        self.assertTrue(paired["step"].startswith("W5. "))
        commands = page_block_after(page, "Then record the same five observations")
        self.assertEqual(paired["observation_commands"], commands)
        self.assertEqual(len(commands), 10)
        for line in commands:
            self.assertNotRegex(line, r"&&|;|\|\|", "five separate commands, not one combined line")
            self.assertIn(line, markdown)
        self.assertTrue(paired["pass_rule"].startswith("Proof: both distributions print the same uid"))
        self.assertIn(paired["pass_rule"], flat_page)
        self.assertIn("prints `masked`", paired["getty_mask"]["proof"])
        self.assertIn(paired["getty_mask"]["proof"], flat_page)
        self.assertTrue(paired["getty_mask"]["commands"])
        for line in paired["getty_mask"]["commands"]:
            self.assertIn("getty@tty1.service", line)
            self.assertIn(line, page)
            self.assertIn(line, markdown)

    def test_each_client_carries_the_three_receipt_fields_in_the_profile_and_the_handbook(self):
        profile = json.loads(self.committed(handbook.PROFILE))
        data = json.loads(self.committed(handbook.OUTPUTS[1]))
        markdown = self.committed(handbook.OUTPUTS[0])
        for name, command in CLIENT_UPDATES.items():
            with self.subTest(client=name):
                entry = next(row for row in profile["entries"] if row["name"] == name)
                tool = next(tool for tool in data["tools"] if tool["name"] == name)
                self.assertEqual(tool["native_update"], entry["native_update"])
                self.assertEqual(entry["native_update"]["command"], command)
                self.assertEqual(set(entry["native_update"]["receipt_fields"]), RECEIPT_FIELDS)
                self.assertIn(f"- {name} native update: `{command}`, UNRUN.", markdown)
                for field in RECEIPT_FIELDS:
                    self.assertIn(f"- {name} receipt field {field}: ", markdown)
        # The bootstrap installs the pin and keeps a newer install; it does not take the current release.
        rule = next(row for row in profile["entries"] if row["name"] == "Claude Code")["version_policy"]
        self.assertIn("keeps a newer existing install", rule)
        for label, text in (("profile", self.committed(handbook.PROFILE)), ("handbook", markdown),
                            ("handbook JSON", self.committed(handbook.OUTPUTS[1])),
                            ("bootstrap page", self.committed("adoption/bootstrap.md"))):
            self.assertNotIn("current at install time", " ".join(text.split()), label)

    def test_the_committed_outputs_are_current_and_the_handbook_receipt_names_them(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_new_wsl_handbook.py"), "--check"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        # The receipt freezes the generator, the profile and both outputs; its hashes follow the regenerated files.
        receipt = json.loads(self.committed("evidence/artifacts/new-wsl-handbook-20261001/receipt.json"))
        profile = json.loads(self.committed(handbook.PROFILE))
        data = json.loads(self.committed(handbook.OUTPUTS[1]))
        self.assertEqual(receipt["generator_sha256"],
                         handbook.digest((ROOT / "scripts/build_new_wsl_handbook.py").read_bytes()))
        self.assertEqual(receipt["profile_sha256"], handbook.digest((ROOT / handbook.PROFILE).read_bytes()))
        self.assertEqual(set(receipt["outputs"]), set(handbook.OUTPUTS))
        for path, digest in receipt["outputs"].items():
            self.assertEqual(digest, handbook.digest((ROOT / path).read_bytes()), path)
        self.assertEqual(receipt["inventory"],
                         {"layers": len(data["layers"]), "profile_entries": len(profile["entries"]),
                          "projected_tools": len(data["tools"]),
                          "canonical_package_ids": sum(1 for tool in data["tools"] if tool.get("package_id"))})

    def test_check_fails_after_a_one_byte_change_to_either_output_or_to_the_manifest(self):
        self.real_tree()
        self.assertEqual(self.public_cli().returncode, 0)
        self.assertEqual(self.public_cli(mode="--check").returncode, 0)
        for path in handbook.OUTPUTS:
            with self.subTest(output=path):
                target = self.root / path
                original = target.read_bytes()
                changed = bytearray(original)
                changed[len(changed) // 2] ^= 1
                target.write_bytes(bytes(changed))
                failed = self.public_cli(mode="--check")
                self.assertEqual(failed.returncode, 1, failed.stdout)
                self.assertIn("stale generated output: " + path, failed.stderr)
                target.write_bytes(original)
                self.assertEqual(self.public_cli(mode="--check").returncode, 0)
        manifest = self.root / DEFAULTS_SOURCE
        original = manifest.read_bytes()
        for label, changed in (("a projected label", original.replace(b'"label": "', b'"label": "X', 1)),
                               ("whitespace only", original + b"\n")):
            with self.subTest(manifest=label):
                self.assertNotEqual(changed, original)
                manifest.write_bytes(changed)
                failed = self.public_cli(mode="--check")
                self.assertEqual(failed.returncode, 1, failed.stdout)
                self.assertIn("stale generated output", failed.stderr)
                manifest.write_bytes(original)
                self.assertEqual(self.public_cli(mode="--check").returncode, 0)


if __name__ == "__main__":
    unittest.main()
