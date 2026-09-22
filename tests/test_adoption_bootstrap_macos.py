"""Static and shimmed checks for the drafted macOS arm64 adoption bootstrap.

No macOS host ran anything here. The script is exercised on Linux through a
temporary PATH shim that makes `uname`/`sw_vers` answer as Apple Silicon macOS,
and only in `--plan` mode: no network access, no download, no installation.
Every assertion below is local_integration or structural evidence; the pinned
checksums themselves are independent observations of publisher checksum files,
release asset digests and re-hashed downloads recorded in the pins file.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PINS_PATH = ROOT / "adoption/pins-macos-arm64.json"
LINUX_PINS_PATH = ROOT / "adoption/pins-linux-x86_64.json"
SCRIPT_PATH = ROOT / "adoption/bootstrap-macos.sh"
MANIFEST_PATH = ROOT / "adoption/manifest.json"
PAGE_PATH = ROOT / "adoption/platforms/macos-arm64.md"
STACK_PATH = ROOT / "manifests/stack.json"

SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")
VALID_KINDS = {"tarball", "zip", "npm"}
VALID_CHECKSUM_SOURCES = {
    "publisher_checksum_file",
    "publisher_checksum_sidecar",
    "github_release_asset_digest_plus_local_rehash",
    "npm_registry_integrity_crosscheck",
}
PROFILE_ID = "macos-arm64-foundation"
# socraticode ships no pinned darwin-arm64 release archive in this draft; it is
# documented as skipped and is deliberately absent from required_commands.
DOCUMENTED_SKIPS = {"socraticode"}
SHELLCHECK = shutil.which("shellcheck")


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def macos_shim(directory: Path) -> Path:
    """A PATH directory whose uname/sw_vers answer as Apple Silicon macOS."""
    shim = directory / "shim"
    shim.mkdir()
    (shim / "uname").write_text(
        "#!/bin/sh\ncase \"$1\" in\n  -s) echo Darwin ;;\n  -m) echo arm64 ;;\n"
        "  *) echo Darwin ;;\nesac\n"
    )
    (shim / "sw_vers").write_text(
        "#!/bin/sh\ncase \"$1\" in\n  -productVersion) echo 15.6 ;;\n"
        "  *) echo 'ProductName:\tmacOS' ;;\nesac\n"
    )
    for name in ("uname", "sw_vers"):
        (shim / name).chmod(0o755)
    return shim


class PinsSchemaTests(unittest.TestCase):
    def setUp(self):
        self.pins = load(PINS_PATH)

    def test_schema_version_platform_and_review_date(self):
        self.assertEqual(self.pins["schema_version"], 1)
        self.assertEqual(self.pins["platform"], "macos-arm64")
        self.assertEqual(self.pins["reviewed_at"], "2026-09-22")
        self.assertTrue(self.pins["source"].strip())

    def test_tools_is_nonempty_and_ids_unique(self):
        tools = self.pins["tools"]
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        ids = [tool["id"] for tool in tools]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate ids in {ids}")

    def test_every_tool_has_required_fields_and_known_kind(self):
        for tool in self.pins["tools"]:
            for field in ("id", "version", "kind", "url", "sha256",
                          "checksum_source", "checksum_ref", "install_note"):
                self.assertIn(field, tool, f"{tool.get('id')} missing {field}")
            self.assertIn(tool["kind"], VALID_KINDS, f"{tool['id']} has unknown kind {tool['kind']}")
            for field in ("install_note", "checksum_ref"):
                self.assertIsInstance(tool[field], str)
                self.assertTrue(tool[field].strip(), f"{tool['id']} has an empty {field}")

    def test_every_sha256_is_lowercase_hex_and_never_null(self):
        for tool in self.pins["tools"]:
            self.assertIsNotNone(tool["sha256"], f"{tool['id']} has a null sha256")
            self.assertRegex(tool["sha256"], SHA256_HEX,
                             f"{tool['id']} sha256 is not 64 lowercase hex chars")

    def test_checksum_source_uses_the_declared_vocabulary(self):
        for tool in self.pins["tools"]:
            self.assertIn(tool["checksum_source"], VALID_CHECKSUM_SOURCES,
                          f"{tool['id']} has an unrecognized checksum_source")

    def test_urls_are_https_and_name_a_darwin_arm64_or_npm_asset(self):
        for tool in self.pins["tools"]:
            self.assertTrue(tool["url"].startswith("https://"), tool["id"])
            if tool["kind"] == "npm":
                self.assertTrue(tool["url"].startswith("https://registry.npmjs.org/"), tool["id"])
            else:
                asset = tool["url"].rsplit("/", 1)[-1]
                self.assertRegex(
                    asset,
                    r"(darwin-arm64|aarch64-apple-darwin|macOS_arm64|macos-aarch64|macos-arm64)",
                    f"{tool['id']} asset {asset} does not name a darwin/arm64 build",
                )

    def test_shared_components_keep_the_linux_pinned_version(self):
        linux = {tool["id"]: tool["version"] for tool in load(LINUX_PINS_PATH)["tools"]}
        for tool in self.pins["tools"]:
            if tool["id"] in linux:
                self.assertEqual(tool["version"], linux[tool["id"]],
                                 f"{tool['id']} version differs from the linux-x86_64 pin")

    def test_npm_pins_reuse_the_linux_registry_tarball_hash(self):
        linux = {tool["id"]: tool for tool in load(LINUX_PINS_PATH)["tools"]}
        npm_ids = [tool["id"] for tool in self.pins["tools"] if tool["kind"] == "npm"]
        self.assertTrue(npm_ids)
        for tool in self.pins["tools"]:
            if tool["kind"] == "npm" and tool["id"] in linux:
                self.assertEqual(tool["sha256"], linux[tool["id"]]["sha256"],
                                 f"{tool['id']} is the same registry tarball; hash must match")

    def test_client_npm_pins_name_their_unpinned_darwin_arm64_dependency(self):
        by_id = {tool["id"]: tool for tool in self.pins["tools"]}
        self.assertIn("@openai/codex-darwin-arm64", by_id["codex"]["install_note"])
        self.assertIn("@anthropic-ai/claude-code-darwin-arm64", by_id["claude-code"]["install_note"])


class ProfileCoverageTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load(MANIFEST_PATH)
        self.pins = load(PINS_PATH)
        self.profile = next(p for p in self.manifest["profiles"] if p["id"] == PROFILE_ID)

    def test_profile_components_are_pinned_except_documented_skips(self):
        pin_ids = {tool["id"] for tool in self.pins["tools"]}
        missing = [cid for cid in self.profile["component_ids"]
                   if cid not in pin_ids and cid not in DOCUMENTED_SKIPS]
        self.assertEqual(missing, [], f"{PROFILE_ID} component_ids without a pin: {missing}")

    def test_every_documented_skip_is_named_on_the_platform_page(self):
        page = PAGE_PATH.read_text()
        for skipped in DOCUMENTED_SKIPS:
            self.assertIn(skipped, page, f"{skipped} is skipped but not documented")
            self.assertNotIn(skipped, self.profile["required_commands"])

    def test_llama_server_is_a_required_command_backed_by_a_pin(self):
        self.assertIn("llama-server", self.profile["required_commands"])
        pin_ids = {tool["id"] for tool in self.pins["tools"]}
        self.assertIn("llama-cpp", pin_ids)

    def test_pinned_ids_stay_a_subset_of_the_stack_components(self):
        components = {item["id"] for item in load(STACK_PATH)["components"]}
        pinned = {tool["id"] for tool in self.pins["tools"]}
        # node, uv and gh are core prerequisites installed by the script itself.
        self.assertTrue(pinned - {"node", "uv", "gh"} <= components)

    def test_platform_profile_row_points_at_this_script_and_pins(self):
        row = next(item for item in self.manifest["platform_profiles"]
                   if item["id"] == "macos-arm64")
        self.assertEqual(row["bootstrap_script"], "adoption/bootstrap-macos.sh")
        self.assertEqual(row["pins"], "adoption/pins-macos-arm64.json")
        self.assertEqual(row["hosted_smoke"], {
            "workflow": ".github/workflows/adoption-bootstrap.yml",
            "job": "bootstrap-macos",
            "status": "pending_first_green_run",
        })
        # The row stays drafted: nothing here is an acceptance.
        self.assertEqual(row["status"], "drafted_not_accepted")
        self.assertIsNone(row["evidence_ref"])
        for reference in (row["bootstrap_script"], row["pins"], row["doc"]):
            self.assertTrue((ROOT / reference).is_file(), reference)


class ScriptStructureTests(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT_PATH.read_text()

    def test_script_is_executable_with_the_expected_shebang_and_strict_mode(self):
        self.assertTrue(SCRIPT_PATH.stat().st_mode & 0o111, "script is not executable")
        self.assertEqual(self.text.splitlines()[0], "#!/usr/bin/env bash")
        self.assertIn("set -Eeuo pipefail", self.text)

    def test_script_guards_darwin_arm64_and_refuses_root(self):
        self.assertIn('"$(uname -s)" == Darwin', self.text)
        self.assertIn('"$(uname -m)" == arm64', self.text)
        self.assertIn('"$EUID" -ne 0', self.text)
        self.assertIn("Run as your normal macOS user, not root.", self.text)

    def test_script_uses_macos_native_tools_only(self):
        self.assertIn("shasum -a 256 --check --status", self.text)
        # Comments may name the Linux tool they replace; only executable lines
        # are checked for a command a stock Mac does not ship.
        code = "\n".join(line for line in self.text.splitlines()
                         if not line.lstrip().startswith("#"))
        for absent in ("sha256sum", "flock", "dpkg-query", "apt-get",
                       "realpath", "mapfile"):
            self.assertNotIn(absent, code, f"{absent} is not available on a stock Mac")
        self.assertIn('pwd -P', self.text)
        self.assertIn('mkdir "$lock_dir"', self.text)

    def test_bin_dir_is_on_path_exactly_once_before_any_pin_is_installed(self):
        path_export_index = self.text.index('export PATH="$bin_dir:$PATH"')
        core_loop_index = self.text.index("for core_id in node uv gh")
        self.assertLess(path_export_index, core_loop_index,
                        "PATH must include bin_dir before node/uv/gh and any npm-kind pin")
        self.assertEqual(self.text.count('export PATH="$bin_dir:$PATH"'), 1)

    def test_llama_server_is_installed_as_a_wrapper_not_a_bare_symlink(self):
        self.assertIn("DYLD_LIBRARY_PATH", self.text)
        # The wrapper lives in a heredoc, so its runtime expansions are escaped
        # in this source file.
        self.assertIn(r'exec "\$llama_prefix/llama-server" "\$@"', self.text)
        self.assertNotIn('ln -sfn "$prefix/llama-server"', self.text)

    def test_version_report_covers_every_placed_executable_and_brew(self):
        self.assertIn('for installed_executable in "$bin_dir"/*', self.text)
        self.assertIn('"$installed_executable" --version', self.text)
        self.assertIn("brew list --versions", self.text)
        self.assertIn('tee "$ecosystem_root/installed-versions.txt"', self.text)

    @unittest.skipUnless(SHELLCHECK, "native shellcheck unavailable; CI installs the pinned analyzer")
    def test_shellcheck_style_is_clean(self):
        result = subprocess.run(
            [SHELLCHECK, "-S", "style", str(SCRIPT_PATH)],
            capture_output=True, text=True, timeout=120, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ScriptBehaviorTests(unittest.TestCase):
    def run_script(self, args, env=None, script=None, timeout=60):
        return subprocess.run(
            ["bash", str(script or SCRIPT_PATH), *args],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, **(env or {})},
        )

    def test_help_exits_zero_without_the_platform_guard(self):
        result = self.run_script(["--help"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--profile", result.stdout)
        self.assertIn("--plan", result.stdout)
        self.assertIn("ECO_INSTALL_ROOT", result.stdout)

    def test_missing_profile_exits_two(self):
        result = self.run_script(["--skip-system-packages"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("--profile", result.stderr)

    def test_unknown_argument_exits_two(self):
        result = self.run_script(["--profile", PROFILE_ID, "--nope"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown argument", result.stderr)

    @unittest.skipIf(os.uname().sysname == "Darwin", "guard check needs a non-macOS host")
    def test_platform_guard_refuses_a_non_macos_host(self):
        result = self.run_script(["--plan", "--profile", PROFILE_ID, "--skip-system-packages"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("Apple Silicon macOS", result.stderr)

    def test_plan_lists_every_pinned_component_without_network_or_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shim = macos_shim(tmp_path)
            eco_root = tmp_path / "eco"
            result = self.run_script(
                ["--plan", "--profile", PROFILE_ID, "--skip-system-packages"],
                env={"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                     "ECO_INSTALL_ROOT": str(eco_root)},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for core in ("node", "uv", "gh"):
                self.assertRegex(result.stdout, rf"(?m)^plan {core}\s")
            for tool in load(PINS_PATH)["tools"]:
                self.assertIn(tool["sha256"], result.stdout, f"{tool['id']} sha256 not planned")
                self.assertIn(tool["url"].rsplit("/", 1)[-1], result.stdout)
            for skipped in DOCUMENTED_SKIPS:
                self.assertIn(f"No pin for component {skipped}", result.stderr)
            self.assertFalse(list(eco_root.glob("tools/*/*")),
                             "plan mode must not install anything")
            self.assertFalse((eco_root / "installed-versions.txt").exists())

    def test_null_hash_pin_is_refused_and_installs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shim = macos_shim(tmp_path)
            adoption_dir = tmp_path / "adoption"
            adoption_dir.mkdir()
            (adoption_dir / "manifest.json").write_text(MANIFEST_PATH.read_text())
            script_copy = adoption_dir / "bootstrap-macos.sh"
            script_copy.write_text(SCRIPT_PATH.read_text())
            script_copy.chmod(0o755)
            pins = load(PINS_PATH)
            pins["tools"][0]["sha256"] = None
            pins["tools"][0]["install_note"] = "test: no reviewed release for this platform yet"
            (adoption_dir / "pins-macos-arm64.json").write_text(json.dumps(pins))
            eco_root = tmp_path / "eco"
            result = self.run_script(
                ["--plan", "--profile", PROFILE_ID, "--skip-system-packages"],
                env={"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                     "ECO_INSTALL_ROOT": str(eco_root)},
                script=script_copy,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Refusing to install", result.stderr)
            self.assertIn("no verified sha256", result.stderr)
            self.assertFalse(list(eco_root.glob("tools/*/*")),
                             "no tool files should have been installed before the refusal")


class PlatformPageTests(unittest.TestCase):
    def setUp(self):
        self.page = PAGE_PATH.read_text()

    def test_page_still_opens_with_the_drafted_heading(self):
        first_line = self.page.splitlines()[0]
        self.assertIn("Drafted, not accepted", first_line)

    def test_page_carries_the_pinned_table_not_a_name_pattern_table(self):
        self.assertNotIn("Expected darwin-arm64 asset name pattern", self.page)
        for tool in load(PINS_PATH)["tools"]:
            self.assertIn(tool["sha256"], self.page, f"{tool['id']} sha256 missing from the page")
            self.assertIn(tool["checksum_source"], self.page)

    def test_page_bounds_what_a_hosted_run_proves(self):
        self.assertIn("What a hosted run proves", self.page)
        self.assertIn("not a workstation acceptance", self.page)
        self.assertIn("launchd", self.page)

    def test_page_records_the_python_313_requirement(self):
        self.assertIn("brew install python@3.13", self.page)
        self.assertIn("3.9", self.page)


if __name__ == "__main__":
    unittest.main()
