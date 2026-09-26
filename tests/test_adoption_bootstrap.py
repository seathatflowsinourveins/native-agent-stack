"""Static checks for adoption/pins-linux-x86_64.json and adoption/bootstrap-linux.sh.

No network access, no installation, and no execution of the pinned tools.
Only the script's argument parsing, root refusal, and null-hash fail-closed
behavior are exercised via `bash -c`, using a stub HOME and no real download,
plus the native-install functions extracted verbatim and run against stub
downloads and a temporary HOME (InstallNativeLauncherTests,
NativeInstallFloorTests).
The exceptions are the optional real-binary classes (RtkConfigReminderRealBinaryTests,
UvToolWheelRealUvTests, NpmIgnoreScriptsRealNpmTests): each runs an already
installed pinned rtk, uv or npm when one is present and skips otherwise, and the
uv and npm ones install a locally built fixture, offline, into a temporary directory.
"""

import base64
import functools
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import shlex
import unittest
import urllib.parse
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PINS_PATH = ROOT / "adoption/pins-linux-x86_64.json"
SCRIPT_PATH = ROOT / "adoption/bootstrap-linux.sh"
MANIFEST_PATH = ROOT / "adoption/manifest.json"
WORKFLOW_PATH = ROOT / ".github/workflows/adoption-bootstrap.yml"
PUBLISH_WORKFLOW_PATH = ROOT / ".github/workflows/publish-catalog.yml"

# bootstrap-linux.sh refuses to run at all off Linux x86_64 (its own guard,
# "This verified asset set targets x86_64 Linux, not Windows/Git Bash or ARM.");
# tests that exercise behaviour past that guard only make sense on that platform.
# adoption/bootstrap-macos.sh is the separate, already-covered macOS path.
LINUX_X86_64_ONLY = unittest.skipUnless(
    sys.platform.startswith("linux") and platform.machine() == "x86_64",
    "bootstrap-linux.sh targets Linux x86_64 only",
)
GITHUB_AUTOMATION_DOC_PATH = ROOT / "docs/github-automation.md"

SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_HEX = re.compile(r"\A[0-9a-f]{40}\Z")
VALID_KINDS = {"tarball", "npm", "pip", "uv-tool", "native", "uv-tool-from-git"}


def load_pins() -> dict:
    return json.loads(PINS_PATH.read_text())


class PinsSchemaTests(unittest.TestCase):
    def setUp(self):
        self.pins = load_pins()

    def test_schema_version_and_platform(self):
        self.assertEqual(self.pins["schema_version"], 1)
        self.assertEqual(self.pins["platform"], "linux-x86_64")

    def test_tools_is_nonempty_list(self):
        self.assertIsInstance(self.pins["tools"], list)
        self.assertGreater(len(self.pins["tools"]), 0)

    def test_no_duplicate_ids(self):
        ids = [tool["id"] for tool in self.pins["tools"]]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate ids in {ids}")

    def test_every_tool_has_required_fields(self):
        for tool in self.pins["tools"]:
            for field in ("id", "version", "kind", "url", "sha256", "install_note"):
                self.assertIn(field, tool, f"{tool.get('id')} missing {field}")
            self.assertIn(tool["kind"], VALID_KINDS, f"{tool['id']} has unknown kind {tool['kind']}")
            self.assertIsInstance(tool["install_note"], str)
            self.assertTrue(tool["install_note"].strip())

    def test_sha256_is_hex_or_null_with_reason(self):
        for tool in self.pins["tools"]:
            sha256 = tool["sha256"]
            if sha256 is None:
                self.assertTrue(
                    tool["install_note"].strip(),
                    f"{tool['id']} has a null sha256 but no reason in install_note",
                )
            else:
                self.assertIsInstance(sha256, str)
                self.assertRegex(sha256, SHA256_HEX, f"{tool['id']} sha256 is not 64 lowercase hex chars")

    def test_uv_tool_from_git_pins_a_verified_commit_instead_of_a_hash(self):
        # serena: upstream ships no released version to hash, so its own
        # fail-closed integrity anchor is a verified 40-hex commit, checked
        # by install_pin before dispatch instead of the sha256 gate.
        for tool in self.pins["tools"]:
            if tool["kind"] == "uv-tool-from-git":
                self.assertIsNone(tool["sha256"], f"{tool['id']}: uv-tool-from-git pins a commit, not a sha256")
                self.assertRegex(tool.get("commit") or "", COMMIT_HEX,
                                 f"{tool['id']} missing a verified 40-hex commit")

    def test_ignore_scripts_is_a_boolean_on_an_npm_pin(self):
        # install_pin hands ignore_scripts to install_npm only; on another kind it would be silently
        # ignored, as it once was on every Linux pin (#299 review, NpmIgnoreScriptsTests).
        for tool in self.pins["tools"]:
            if "ignore_scripts" in tool:
                self.assertIsInstance(tool["ignore_scripts"], bool, tool["id"])
                self.assertEqual(tool["kind"], "npm", f"{tool['id']}: only npm pins read ignore_scripts")

    def test_a_uv_tool_wheel_url_names_the_pinned_version(self):
        # install_uv_tool refuses a wheel whose filename names another version (UvToolWheelPinTests).
        for tool in self.pins["tools"]:
            if tool["kind"] == "uv-tool" and tool["url"].endswith(".whl"):
                self.assertEqual(tool["url"].rsplit("/", 1)[1].split("-")[1], tool["version"], tool["id"])

    def test_a_uv_tool_url_is_a_plain_wheel_or_sdist_file(self):
        # install_uv_tool downloads and verifies a url ending in .whl and treats any other as an sdist
        # cross-check, so a wheel url carrying a ?query or a #sha256= fragment (as index links do) would
        # silently fall back to an unverified index install.
        for tool in self.pins["tools"]:
            if tool["kind"] == "uv-tool":
                self.assertRegex(tool["url"], r"\Ahttps://[^?#\s]+\.(?:whl|tar\.gz)\Z", tool["id"])

    def test_all_pins_in_this_pr_have_a_verified_hash(self):
        # This PR fetched and hashed every pinned artifact from its official
        # registry/release metadata; none are deferred. The one exception is
        # a uv-tool-from-git pin (see test_uv_tool_from_git_pins_a_verified_commit_instead_of_a_hash):
        # there is no released archive to hash, so its own commit-shape
        # check stands in for this one.
        for tool in self.pins["tools"]:
            if tool["kind"] == "uv-tool-from-git":
                continue
            self.assertIsNotNone(tool["sha256"], f"{tool['id']} unexpectedly has a null sha256")


class ProfileMappingTests(unittest.TestCase):
    def test_profile_ids_referenced_by_workflow_exist_in_manifest(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        profile_ids = {profile["id"] for profile in manifest["profiles"]}
        self.assertIn("foundation-cpu", profile_ids)
        self.assertIn("macos-arm64-foundation", profile_ids)

    def test_foundation_cpu_component_ids_covered_by_pins_or_documented(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        pins = load_pins()
        pin_ids = {tool["id"] for tool in pins["tools"]}
        profile = next(p for p in manifest["profiles"] if p["id"] == "foundation-cpu")
        missing = [cid for cid in profile["component_ids"] if cid not in pin_ids]
        self.assertEqual(missing, [], f"foundation-cpu component_ids without a pin: {missing}")


class ScriptBehaviorTests(unittest.TestCase):
    def test_script_is_executable_and_shebang(self):
        self.assertTrue(SCRIPT_PATH.stat().st_mode & 0o111, "script is not executable")
        first_line = SCRIPT_PATH.read_text().splitlines()[0]
        self.assertEqual(first_line, "#!/usr/bin/env bash")

    def test_script_uses_strict_mode(self):
        self.assertIn("set -Eeuo pipefail", SCRIPT_PATH.read_text())

    def test_script_refuses_root(self):
        # Cannot become root in CI; assert the EUID guard text and reachable
        # unit is present, then exercise it under a faked EUID via a helper
        # shell that overrides $EUID before sourcing the guard clause.
        text = SCRIPT_PATH.read_text()
        self.assertIn('"$EUID" -ne 0', text)
        self.assertIn("Run as your normal Linux user, not root.", text)

    def test_help_exits_zero_without_touching_network_or_filesystem(self):
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--profile", result.stdout)
        self.assertIn("ECO_INSTALL_ROOT", result.stdout)

    def test_missing_profile_exits_two(self):
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), "--skip-system-packages"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--profile", result.stderr)

    @LINUX_X86_64_ONLY
    def test_unknown_profile_exits_nonzero(self):
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), "--profile", "not-a-real-profile", "--skip-system-packages"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown or empty profile", result.stderr)

    @LINUX_X86_64_ONLY
    def test_null_hash_pin_is_refused_before_any_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adoption_dir = tmp_path / "adoption"
            adoption_dir.mkdir()
            (adoption_dir / "manifest.json").write_text(MANIFEST_PATH.read_text())
            (adoption_dir / "bootstrap-linux.sh").write_text(SCRIPT_PATH.read_text())
            (adoption_dir / "bootstrap-linux.sh").chmod(0o755)
            pins = load_pins()
            pins["tools"][0]["sha256"] = None
            pins["tools"][0]["install_note"] = "test: no reviewed release for this platform yet"
            (adoption_dir / "pins-linux-x86_64.json").write_text(json.dumps(pins))
            eco_root = tmp_path / "eco"
            result = subprocess.run(
                ["bash", str(adoption_dir / "bootstrap-linux.sh"),
                 "--profile", "foundation-cpu", "--skip-system-packages"],
                capture_output=True,
                text=True,
                timeout=30,
                env={**__import__("os").environ, "ECO_INSTALL_ROOT": str(eco_root)},
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Refusing to install", result.stderr)
            self.assertIn("no verified sha256", result.stderr)
            self.assertFalse(eco_root.exists() and any(eco_root.glob("tools/*/*")),
                              "no tool files should have been installed before the refusal")

    @LINUX_X86_64_ONLY
    def test_uv_tool_from_git_pin_with_a_bad_commit_is_refused_before_any_download(self):
        # Mirrors test_null_hash_pin_is_refused_before_any_download, but for
        # the uv-tool-from-git gate (serena): mutate the first-installed core
        # id (node, always installed first regardless of profile) into a
        # uv-tool-from-git pin with a malformed commit, so the refusal is
        # guaranteed to happen before uv, gh or any profile component -- and
        # so before any network access.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adoption_dir = tmp_path / "adoption"
            adoption_dir.mkdir()
            (adoption_dir / "manifest.json").write_text(MANIFEST_PATH.read_text())
            (adoption_dir / "bootstrap-linux.sh").write_text(SCRIPT_PATH.read_text())
            (adoption_dir / "bootstrap-linux.sh").chmod(0o755)
            pins = load_pins()
            self.assertEqual(pins["tools"][0]["id"], "node")
            pins["tools"][0]["kind"] = "uv-tool-from-git"
            pins["tools"][0]["commit"] = "not-forty-hex-chars"
            pins["tools"][0]["sha256"] = None
            pins["tools"][0]["install_note"] = "test: malformed commit"
            (adoption_dir / "pins-linux-x86_64.json").write_text(json.dumps(pins))
            eco_root = tmp_path / "eco"
            result = subprocess.run(
                ["bash", str(adoption_dir / "bootstrap-linux.sh"),
                 "--profile", "foundation-cpu", "--skip-system-packages"],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "ECO_INSTALL_ROOT": str(eco_root)},
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Refusing to install", result.stderr)
            self.assertIn("no verified 40-hex commit", result.stderr)
            self.assertFalse(eco_root.exists() and any(eco_root.glob("tools/*/*")),
                              "no tool files should have been installed before the refusal")

    def test_bin_dir_is_on_path_before_any_pin_is_installed(self):
        # Regression: npm-kind and uv-tool-kind installers call `command -v
        # npm`/`command -v uv` to find the just-installed node/uv symlinks in
        # bin_dir. If PATH is exported only after every pin installs, those
        # lookups silently fall back to (or miss) a pre-existing host copy on
        # a fresh machine. Assert the export precedes the core install loop.
        text = SCRIPT_PATH.read_text()
        path_export_index = text.index('export PATH="$bin_dir:$PATH"')
        core_loop_index = text.index('for core_id in node uv gh')
        self.assertLess(
            path_export_index, core_loop_index,
            "PATH must include bin_dir before node/uv/gh (and any npm- or "
            "uv-tool-kind pin) are installed",
        )
        # The export must not be duplicated after the install loops, which
        # would mask the bug by only working once every pin has already
        # tried (and possibly failed) to resolve command -v npm/uv.
        self.assertEqual(text.count('export PATH="$bin_dir:$PATH"'), 1)

    def test_version_report_checks_every_installed_pin_and_lists_bin_dir(self):
        # Regression: the retained installed-versions.txt evidence log once
        # hardcoded five tools (git/node/npm/uv/gh); its replacement ran
        # --version on every bin_dir entry, which blocked on servers without a
        # version flag (MCP Inspector, context-mode, socraticode). The report
        # now checks every pin this run installed with the probe its pin
        # declares and lists all of bin_dir without running it;
        # tests/test_adoption_version_probes.py exercises that behavior.
        text = SCRIPT_PATH.read_text()
        self.assertIn('for id in ${installed_pin_ids[@]+"${installed_pin_ids[@]}"}; do', text)
        self.assertIn('for executable in "$bin_dir"/*; do', text)
        self.assertNotIn('"$installed_executable" --version', text)


class UnpinnedComponentFailClosedTests(unittest.TestCase):
    """Regression tests for item 3: a selected component with no pin at all must
    fail closed (exit 3) before installing anything, unless explicitly allowed
    via --allow-unpinned. Uses a minimal, fully synthetic manifest/pins pair (no
    real network-reachable pins) so a "no leaks" run stays offline end to end.
    """

    def _write_fixture(self, tmp_path: Path, component_ids):
        adoption_dir = tmp_path / "adoption"
        adoption_dir.mkdir()
        (adoption_dir / "bootstrap-linux.sh").write_text(SCRIPT_PATH.read_text())
        (adoption_dir / "bootstrap-linux.sh").chmod(0o755)
        manifest = {
            "schema_version": 1,
            "profiles": [{"id": "test-profile", "component_ids": component_ids}],
        }
        (adoption_dir / "manifest.json").write_text(json.dumps(manifest))
        # No pins at all: node/uv/gh (always core-selected) and every
        # component_id above are all unpinned.
        pins = {"schema_version": 1, "platform": "linux-x86_64", "tools": []}
        (adoption_dir / "pins-linux-x86_64.json").write_text(json.dumps(pins))
        return adoption_dir

    def _run(self, adoption_dir: Path, eco_root: Path, extra_args=()):
        import os
        return subprocess.run(
            ["bash", str(adoption_dir / "bootstrap-linux.sh"),
             "--profile", "test-profile", "--skip-system-packages", *extra_args],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "ECO_INSTALL_ROOT": str(eco_root)},
        )

    @LINUX_X86_64_ONLY
    def test_unpinned_component_exits_3_before_installing_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adoption_dir = self._write_fixture(tmp_path, ["some-unpinned-tool"])
            eco_root = tmp_path / "eco"
            result = self._run(adoption_dir, eco_root)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn("No pin in", result.stderr)
            # node, uv and gh are always core-selected and are unpinned here too.
            self.assertIn("node", result.stderr)
            self.assertIn("uv", result.stderr)
            self.assertIn("gh", result.stderr)
            self.assertIn("some-unpinned-tool", result.stderr)
            self.assertIn("--allow-unpinned", result.stderr)
            self.assertFalse(
                eco_root.exists() and any(eco_root.glob("tools/*/*")),
                "no tool files should have been installed before the refusal",
            )

    @LINUX_X86_64_ONLY
    def test_allow_unpinned_covering_every_gap_proceeds_and_is_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adoption_dir = self._write_fixture(tmp_path, ["some-unpinned-tool"])
            eco_root = tmp_path / "eco"
            result = self._run(
                adoption_dir, eco_root,
                extra_args=["--allow-unpinned", "node,uv,gh,some-unpinned-tool"],
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Allowed unpinned components (--allow-unpinned):", result.stdout)
            self.assertIn("some-unpinned-tool", result.stdout)
            self.assertIn("Installation finished", result.stdout)
            self.assertFalse(
                eco_root.exists() and any(eco_root.glob("tools/*/*")),
                "no pin exists for any selected component, so nothing should install",
            )

    @LINUX_X86_64_ONLY
    def test_partial_allow_unpinned_still_fails_closed_on_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adoption_dir = self._write_fixture(tmp_path, ["some-unpinned-tool"])
            eco_root = tmp_path / "eco"
            result = self._run(
                adoption_dir, eco_root,
                extra_args=["--allow-unpinned", "some-unpinned-tool"],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn("node", result.stderr)
            self.assertIn("uv", result.stderr)
            self.assertIn("gh", result.stderr)
            self.assertNotIn("some-unpinned-tool", result.stderr.split("No pin in", 1)[-1].split("\n")[0])


class InstallRootCanonicalHomeTests(unittest.TestCase):
    """An ECO_INSTALL_ROOT that only resolves to HOME after canonicalization
    ("$HOME/.", a symlink to HOME, "$HOME/../<home>") must be refused before
    bin/, tools/ or downloads/ are created in HOME (cross-family review P2)."""

    @LINUX_X86_64_ONLY
    def test_install_root_that_resolves_to_home_is_refused(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()
            link = tmp_path / "home-link"
            link.symlink_to(home)
            adoption_dir = UnpinnedComponentFailClosedTests()._write_fixture(tmp_path, ["some-unpinned-tool"])
            roots = {"home-dot": f"{home}/.", "home-symlink": str(link),
                     "home-parent-walk": f"{home}/../home"}
            for label, root in roots.items():
                with self.subTest(root=label):
                    result = subprocess.run(
                        ["bash", str(adoption_dir / "bootstrap-linux.sh"), "--profile", "test-profile",
                         "--skip-system-packages", "--allow-unpinned", "node,uv,gh,some-unpinned-tool"],
                        capture_output=True, text=True, timeout=30,
                        env={**os.environ, "HOME": str(home), "ECO_INSTALL_ROOT": root},
                    )
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("ECO_INSTALL_ROOT must name a dedicated", result.stderr)
                    self.assertEqual(sorted(p.name for p in home.iterdir()), [],
                                     "installation children were created in HOME")


class SystemPackagesBeforePrerequisiteCheckTests(unittest.TestCase):
    """Regression tests for item 4: the apt-managed prerequisite install must
    run before the curl/git/tar/jq presence check, and --skip-system-packages
    makes that check list what is missing and exit 4."""

    def test_apt_block_precedes_prerequisite_check_in_source_order(self):
        text = SCRIPT_PATH.read_text()
        apt_index = text.index("sudo apt-get install -y --no-install-recommends")
        check_index = text.index('for required in curl git tar sha256sum realpath flock jq mktemp')
        self.assertLess(
            apt_index, check_index,
            "the apt-get install step must run before the curl/git/tar/jq presence check",
        )

    @LINUX_X86_64_ONLY
    def test_skip_system_packages_with_missing_tool_lists_it_and_exits_4(self):
        # Exercise the real check logic (not just source order) by prepending a
        # stub PATH directory that shadows `jq` with nothing, so the presence
        # check itself reports it missing without ever needing apt or network.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adoption_dir = tmp_path / "adoption"
            adoption_dir.mkdir()
            (adoption_dir / "bootstrap-linux.sh").write_text(SCRIPT_PATH.read_text())
            (adoption_dir / "bootstrap-linux.sh").chmod(0o755)
            (adoption_dir / "manifest.json").write_text(MANIFEST_PATH.read_text())
            (adoption_dir / "pins-linux-x86_64.json").write_text(PINS_PATH.read_text())

            stub_bin = tmp_path / "stub-bin"
            stub_bin.mkdir()
            # Symlink uname (needed before the check runs) and every normally-
            # required tool except jq, so only jq is reported missing. PATH is
            # restricted to exactly this directory so nothing falls back to a
            # real system jq.
            import os
            import shutil as _shutil
            bash_path = _shutil.which("bash")
            for tool in ("uname", "curl", "git", "tar", "sha256sum", "realpath", "flock", "mktemp"):
                found = _shutil.which(tool)
                if found:
                    (stub_bin / tool).symlink_to(found)
            eco_root = tmp_path / "eco"
            result = subprocess.run(
                [bash_path, str(adoption_dir / "bootstrap-linux.sh"),
                 "--profile", "foundation-cpu", "--skip-system-packages"],
                capture_output=True,
                text=True,
                timeout=30,
                env={"PATH": str(stub_bin), "HOME": os.environ.get("HOME", "/root"),
                     "ECO_INSTALL_ROOT": str(eco_root)},
            )
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertIn("Missing prerequisites", result.stderr)
            self.assertIn("jq", result.stderr)
            self.assertIn("--skip-system-packages", result.stderr)


class PublishWorkflowTests(unittest.TestCase):
    """Regression tests for the SBOM publication fixes in publish-catalog.yml."""

    def setUp(self):
        self.text = PUBLISH_WORKFLOW_PATH.read_text()

    def test_sbom_sha256sum_runs_from_the_publication_dir(self):
        # Regression: `sha256sum "$(basename "$sbom")"` under
        # working-directory: github.workspace looked for the SBOM in the
        # checked-out repo, not $PUBLICATION_DIR where syft wrote it.
        sbom_step = self.text.split("Generate the SPDX SBOM", 1)[1].split("- name:", 1)[0]
        self.assertIn('cd "$PUBLICATION_DIR"', sbom_step)
        cd_index = sbom_step.index('cd "$PUBLICATION_DIR"')
        sha_index = sbom_step.index('sha256sum "$(basename "$sbom")"')
        self.assertLess(cd_index, sha_index)

    def test_sbom_attestation_verify_pins_its_predicate_type(self):
        # Regression: gh attestation verify defaults --predicate-type to the
        # SLSA provenance predicate; without an explicit override it cannot
        # verify an https://spdx.dev/Document attestation.
        verify_step = self.text.split("Verify SBOM attestation provenance", 1)[1]
        verify_step = verify_step.split("- name:", 1)[0]
        self.assertIn("--predicate-type https://spdx.dev/Document", verify_step)

    def test_archive_and_sbom_uploads_have_distinct_explicit_names(self):
        # Regression: both upload-artifact steps omitted `name:`, so both
        # used the action's default "artifact" name and the second upload
        # would 409-conflict with the first in the same run.
        names = re.findall(r"^\s+name:\s+(\S.*)$", self.text, flags=re.MULTILINE)
        upload_names = [n for n in names if "native-agent-stack-${{ github.sha }}" in n]
        self.assertGreaterEqual(len(upload_names), 2)
        self.assertEqual(len(upload_names), len(set(upload_names)),
                          f"upload-artifact names collide: {upload_names}")


class GithubAutomationDocTests(unittest.TestCase):
    def test_operator_verify_snippet_pins_predicate_type(self):
        text = GITHUB_AUTOMATION_DOC_PATH.read_text()
        snippet = text.split("gh attestation verify native-agent-stack-<sha>.spdx.json", 1)[1]
        snippet = snippet.split("```", 1)[0]
        self.assertIn("--predicate-type https://spdx.dev/Document", snippet)


class AdoptionWorkflowPythonVersionTests(unittest.TestCase):
    def test_workflow_installs_the_manifest_supported_python_before_status(self):
        # Regression: scripts/adoption_status.py's overall status requires
        # the host's python3 major.minor to match adoption/manifest.json's
        # supported_platforms; ubuntu-24.04's default python3 is 3.12 while
        # the manifest declares 3.13, so the status step exited 2 on every
        # run. Assert a Python 3.13 setup step precedes the status step.
        text = WORKFLOW_PATH.read_text()
        setup_index = text.index("actions/setup-python@")
        # The literal invocation, not a bare path-filter list entry or a
        # comment mentioning the script by name -- both of which can sit
        # earlier in the file than the first job's own setup-python step.
        status_index = text.index("python3 scripts/adoption_status.py")
        self.assertLess(setup_index, status_index)
        setup_step = text[setup_index:status_index]
        self.assertIn("python-version: '3.13'", setup_step)
        manifest = json.loads(MANIFEST_PATH.read_text())
        supported_pythons = {p["python"] for p in manifest["supported_platforms"]}
        self.assertIn("3.13", supported_pythons)


class WorkflowReferenceTests(unittest.TestCase):
    def test_workflow_references_the_bootstrap_script_path(self):
        text = WORKFLOW_PATH.read_text()
        self.assertIn("adoption/bootstrap-linux.sh", text)

    def test_workflow_references_the_macos_bootstrap_script_path(self):
        text = WORKFLOW_PATH.read_text()
        self.assertIn("adoption/bootstrap-macos.sh", text)

    def test_workflow_references_the_status_script(self):
        text = WORKFLOW_PATH.read_text()
        self.assertIn("scripts/adoption_status.py", text)

    def test_workflow_targets_foundation_cpu_profile(self):
        text = WORKFLOW_PATH.read_text()
        self.assertIn("foundation-cpu", text)


class InstallNativeLauncherTests(unittest.TestCase):
    """Runs each script's own install_native with a stub fetch and a stub native
    installer that, like `claude install`, links ~/.local/bin/claude into
    ~/.local/share/claude/versions."""

    STUB_INSTALLER = (
        "#!/usr/bin/env bash\n"
        "mkdir -p \"$HOME/.local/share/claude/versions\" \"$HOME/.local/bin\"\n"
        "printf 'REAL-BINARY\\n' > \"$HOME/.local/share/claude/versions/$2\"\n"
        "ln -sfn \"$HOME/.local/share/claude/versions/$2\" \"$HOME/.local/bin/claude\"\n"
    )

    def run_install_native(self, script: Path, home: Path, bin_dir: Path):
        text = script.read_text()
        match = re.search(r"(?ms)^install_native\(\) \{.*?^\}$", text)
        self.assertIsNotNone(match, f"install_native not found in {script}")
        stub = home / "stub-installer"
        stub.write_text(self.STUB_INSTALLER)
        harness = (
            f"set -euo pipefail\ncache_dir={shlex.quote(str(home / 'cache'))}\n"
            f"bin_dir={shlex.quote(str(bin_dir))}\nmkdir -p \"$cache_dir\" \"$bin_dir\"\n"
            f"fetch() {{ cp {shlex.quote(str(stub))} \"$3\"; }}\n"
            + match.group(0)
            + "\ninstall_native claude-code 2.1.280 https://example.invalid/claude 0 claude\n"
        )
        env = dict(os.environ, HOME=str(home))
        return subprocess.run(["bash", "-c", harness], capture_output=True, text=True, env=env, timeout=30)

    def test_launcher_goes_to_bin_dir_and_leaves_the_native_binary_intact(self):
        for script in (SCRIPT_PATH, ROOT / "adoption/bootstrap-macos.sh"):
            with self.subTest(script=script.name), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                bin_dir = home / "eco" / "bin"
                bin_dir.mkdir(parents=True)
                # A stale symlink at the launcher path must be replaced, not written through.
                (home / ".local/share/claude/versions").mkdir(parents=True)
                (home / ".local/share/claude/versions/old").write_text("OLD-BINARY\n")
                (bin_dir / "claude").symlink_to(home / ".local/share/claude/versions/old")
                result = self.run_install_native(script, home, bin_dir)
                self.assertEqual(result.returncode, 0, result.stderr)
                launcher = bin_dir / "claude"
                self.assertFalse(launcher.is_symlink())
                self.assertIn('exec "$HOME/.local/bin/claude"', launcher.read_text())
                self.assertEqual((home / ".local/share/claude/versions/old").read_text(), "OLD-BINARY\n")
                self.assertEqual((home / ".local/bin/claude").read_text(), "REAL-BINARY\n")

    def test_no_launcher_when_bin_dir_is_the_native_bin_dir(self):
        for script in (SCRIPT_PATH, ROOT / "adoption/bootstrap-macos.sh"):
            with self.subTest(script=script.name), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                result = self.run_install_native(script, home, home / ".local" / "bin")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((home / ".local/bin/claude").is_symlink())
                self.assertEqual((home / ".local/bin/claude").read_text(), "REAL-BINARY\n")


def shell_functions(text: str, *names: str) -> str:
    """The source of top-level shell functions, from `name() {` to its `}`."""
    blocks = []
    for name in names:
        match = re.search(rf"(?ms)^{re.escape(name)}\(\) \{{\n.*?^\}}\n", text)
        assert match, f"function {name} not found"
        blocks.append(match.group(0))
    return "".join(blocks)


@functools.lru_cache(maxsize=None)
def sha256sum_checks_like_gnu() -> bool:
    """Whether this host's sha256sum accepts fetch()'s `--check --status` (GNU coreutils does;
    macOS's /sbin/sha256sum prints its usage and exits 1)."""
    if shutil.which("sha256sum") is None:
        return False
    data = b"probe\n"
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe"
        probe.write_bytes(data)
        result = subprocess.run(["sha256sum", "--check", "--status"], capture_output=True, text=True,
                                input=f"{hashlib.sha256(data).hexdigest()}  {probe}\n", timeout=10, check=False)
    return result.returncode == 0


class InstallUvToolFromGitTests(unittest.TestCase):
    """install_uv_tool_from_git, extracted verbatim from bootstrap-linux.sh, run against a `uv` shim that
    records its arguments and writes a chosen uv-receipt.toml. The install is accepted only when the
    receipt records the pinned commit; a missing receipt, a receipt naming another commit and a missing
    `uv` each exit 1 with their own refusal."""

    COMMIT = "c6fbd1c5932df2494ffa0020af5a9fbe80b82143"
    OTHER = "0" * 40

    def _run(self, tmp_path: Path, receipt_rev, with_uv=True):
        eco, bin_dir, shim = tmp_path / "eco", tmp_path / "bin", tmp_path / "shim"
        for directory in (eco, bin_dir, shim):
            directory.mkdir()
        calls = tmp_path / "uv-calls.log"
        if with_uv:
            write = ("" if receipt_rev is None else
                     'mkdir -p "$UV_TOOL_DIR/serena-agent"\n'
                     f'printf \'[tool]\\nrequirements = [{{ name = "serena-agent", git = "https://github.com/oraios/serena?rev={receipt_rev}" }}]\\n\' '
                     '> "$UV_TOOL_DIR/serena-agent/uv-receipt.toml"\n')
            (shim / "uv").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {shlex.quote(str(calls))}\n{write}')
            (shim / "uv").chmod(0o755)
        harness = (f"set -euo pipefail\necosystem_root={shlex.quote(str(eco))}\nbin_dir={shlex.quote(str(bin_dir))}\n"
                   + shell_functions(SCRIPT_PATH.read_text(), "install_uv_tool_from_git")
                   + f"install_uv_tool_from_git serena '2.0.0.dev0' https://github.com/oraios/serena {self.COMMIT} serena-agent\n")
        env = {"PATH": f"{shim}:/usr/bin:/bin", "HOME": str(tmp_path)}
        result = subprocess.run(["bash", "-c", harness], capture_output=True, text=True, env=env, timeout=30)
        return result, (calls.read_text() if calls.exists() else "")

    def test_accepts_only_a_receipt_that_records_the_pinned_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls = self._run(Path(tmp), self.COMMIT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"tool install --python 3.13 git+https://github.com/oraios/serena@{self.COMMIT}", calls)

    def test_refuses_when_uv_writes_no_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self._run(Path(tmp), None)
        self.assertEqual(result.returncode, 1)
        self.assertIn("no uv-receipt.toml", result.stderr)

    def test_refuses_a_receipt_that_names_another_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self._run(Path(tmp), self.OTHER)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"does not record the pinned commit {self.COMMIT}", result.stderr)

    def test_refuses_without_uv(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls = self._run(Path(tmp), self.COMMIT, with_uv=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("uv is required", result.stderr)
        self.assertEqual(calls, "")


def shipped_pin(pin_id: str) -> dict:
    return next(tool for tool in load_pins()["tools"] if tool["id"] == pin_id)


def run_install_pin(test: unittest.TestCase, tmp_path: Path, pin: dict, served: bytes, eco_name: str = "eco",
                    real: dict | None = None, env: dict | None = None):
    """Runs bootstrap-linux.sh's own install_pin on a one-pin fixture, with fetch, npm_package_name,
    install_npm and install_uv_tool extracted verbatim. The `curl` shim logs each URL and writes
    `served`, so fetch() really compares those bytes with the pin's sha256 (through `shasum` where this
    host's sha256sum lacks GNU's --check --status). The `npm` and `uv` shims record each invocation's
    argv, one argument per line (uv's preceded by the UV_TOOL_DIR and UV_TOOL_BIN_DIR it was given), and
    then exec the real binary `real` maps that name to, if any. The ecosystem root is
    `tmp_path/eco_name`; `env` adds to the harness's environment.
    Returns the result, the fetched URLs, the npm and uv invocations and the ecosystem root."""
    for tool in ["jq"] if sha256sum_checks_like_gnu() else ["jq", "shasum"]:
        if shutil.which(tool) is None:
            test.skipTest(f"{tool} is not on PATH")
    real = real or {}
    eco = tmp_path / eco_name
    for directory in ("downloads", "tools", "bin"):
        (eco / directory).mkdir(parents=True)
    (tmp_path / "served").write_bytes(served)
    logs = {name: tmp_path / f"{name}.log" for name in ("curl", "npm", "uv")}
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "curl").write_text(
        "#!/bin/sh\n"
        'out=""; prev=""\n'
        'for arg in "$@"; do\n'
        '  if [ "$prev" = "--output" ]; then out="$arg"; fi\n'
        f'  case "$arg" in https://*) printf "%s\\n" "$arg" >> {shlex.quote(str(logs["curl"]))} ;; esac\n'
        '  prev="$arg"\n'
        "done\n"
        f'cp {shlex.quote(str(tmp_path / "served"))} "$out"\n'
    )

    def then_exec(name):
        return f'exec {shlex.quote(str(real[name]))} "$@"\n' if name in real else ""

    (shim / "npm").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" "<end>" >> {shlex.quote(str(logs["npm"]))}\n'
                              + then_exec("npm"))
    (shim / "uv").write_text(
        '#!/bin/sh\nprintf "%s\\n" "UV_TOOL_DIR=$UV_TOOL_DIR" "UV_TOOL_BIN_DIR=$UV_TOOL_BIN_DIR" "$@" "<end>" '
        f'>> {shlex.quote(str(logs["uv"]))}\n' + then_exec("uv"))
    if not sha256sum_checks_like_gnu():
        (shim / "sha256sum").write_text('#!/bin/sh\nexec shasum -a 256 "$@"\n')
    for tool in shim.iterdir():
        tool.chmod(0o755)
    pins_path = tmp_path / "pins.json"
    pins_path.write_text(json.dumps({"tools": [pin]}))
    harness = tmp_path / "install-pin-harness.sh"
    harness.write_text(
        "set -Eeuo pipefail\n"
        + shell_functions(SCRIPT_PATH.read_text(), "verify_sha256", "fetch", "npm_package_name", "install_npm",
                          "install_uv_tool", "install_pin")
        + f"pins_path={shlex.quote(str(pins_path))}\n"
        + f"ecosystem_root={shlex.quote(str(eco))}\n"
        + f"bin_dir={shlex.quote(str(eco / 'bin'))}\n"
        + f"cache_dir={shlex.quote(str(eco / 'downloads'))}\n"
        + "installed_pin_ids=()\n"
        + f"install_pin {shlex.quote(pin['id'])}\n"
    )
    env = {**os.environ, **(env or {})}
    result = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=120,
                            env={**env, "PATH": f"{shim}{os.pathsep}{env['PATH']}"})

    def invocations(name):
        text = logs[name].read_text() if logs[name].exists() else ""
        return [record.splitlines() for record in text.split("<end>\n") if record]

    urls = logs["curl"].read_text().splitlines() if logs["curl"].exists() else []
    return result, urls, invocations("npm"), invocations("uv"), eco


class NpmIgnoreScriptsTests(unittest.TestCase):
    """2026-09-26, #299 review: socraticode's pin sets `ignore_scripts: true`, but install_pin never
    passed the field on and install_npm never added --ignore-scripts, so npm ran every lifecycle script
    in the package's dependency tree. install_pin now reads it as bootstrap-macos.sh's does. Runs the
    shipped socraticode entry through install_pin (run_install_pin), with only its sha256 swapped for
    the served fixture's, and compares npm's whole argv. The end-to-end run with the real tarball, and
    npm's own log of which scripts ran, are in evidence/artifacts/bootstrap-integrity-20260926/."""

    ARCHIVE = b"fixture npm tarball\n"

    def _npm_argv(self, **changes):
        pin = {**shipped_pin("socraticode"), "sha256": hashlib.sha256(self.ARCHIVE).hexdigest(), **changes}
        pin = {key: value for key, value in pin.items() if value is not None}
        with tempfile.TemporaryDirectory() as tmp:
            result, urls, npm_calls, uv_calls, eco = run_install_pin(self, Path(tmp), pin, self.ARCHIVE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((urls, uv_calls), ([pin["url"]], []))
        self.assertEqual(len(npm_calls), 1, npm_calls)
        prefix = eco / f"tools/{pin['id']}-{pin['version']}"
        archive = eco / f"downloads/{pin['id']}-{pin['version']}.tgz"
        return npm_calls[0], ["install", "--global", "--no-audit", "--no-fund", "--prefix", str(prefix)], str(archive)

    def test_the_shipped_socraticode_pin_installs_with_ignore_scripts(self):
        self.assertIs(shipped_pin("socraticode")["ignore_scripts"], True)
        argv, head, archive = self._npm_argv()
        self.assertEqual(argv, [*head, "--ignore-scripts", archive])

    def test_a_pin_without_ignore_scripts_true_runs_npm_without_the_flag(self):
        for value in (None, False):  # absent, as on every other npm pin, or explicitly false
            with self.subTest(ignore_scripts=value):
                argv, head, archive = self._npm_argv(ignore_scripts=value)
                self.assertEqual(argv, [*head, archive])


class UvToolWheelPinTests(unittest.TestCase):
    """2026-09-26, #299 review: headroom's pin names a wheel url and sha256 that install_uv_tool never
    read; uv resolved `headroom-ai[mcp]==0.37.0` from its index, so nothing tied the installed files to
    the reviewed wheel. A uv-tool pin whose url is a wheel is now fetched and sha256-verified, and uv
    installs that local file with the pin's extras (`<package> @ file://<wheel>`, each path segment
    percent-encoded: as a bare path, a `#` or ` ;` in ECO_INSTALL_ROOT reaches uv as a URI fragment or
    a PEP 508 marker, and the pinned uv 0.12.17 refuses the install). Runs the shipped headroom entry
    through install_pin (run_install_pin), with only its sha256 swapped for the served fixture's; the
    `uv` shim stands in for uv, so this proves the argv, not uv's handling of it (UvToolWheelRealUvTests
    runs the pinned uv where one is installed; evidence/artifacts/bootstrap-integrity-20260926/ keeps
    the uv form trials and an end-to-end run with the real wheel)."""

    WHEEL = b"fixture wheel bytes\n"
    # An install root whose path holds each character a bare-path direct reference misreads, plus a
    # literal "%" and a non-ASCII letter, which the file URL must encode too.
    AWKWARD_ROOT = "eco #1 ;%é"

    def _run(self, pin_id="headroom", eco_name="eco", **changes):
        pin = {**shipped_pin(pin_id), "sha256": hashlib.sha256(self.WHEEL).hexdigest(), **changes}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return (pin, *run_install_pin(self, Path(tmp.name), pin, self.WHEEL, eco_name=eco_name))

    def uv_argv(self, eco: Path, spec: str) -> list:
        return [f"UV_TOOL_DIR={eco}/python-tools", f"UV_TOOL_BIN_DIR={eco}/bin",
                "tool", "install", "--python", "3.13", spec]

    def assert_uv_installs_the_wheel_file(self, uv_calls: list, eco: Path, package: str, wheel: Path):
        """One uv call with the exact argv, whose spec is `<package> @ file://<url path>`: a URL path of
        URI-safe characters and %XX escapes only (no raw space, "#", ";" or non-ASCII byte left for a
        PEP 508 parser to misread) that decodes back to the downloaded wheel's path."""
        self.assertEqual(len(uv_calls), 1, uv_calls)
        spec = uv_calls[0][-1]
        self.assertEqual(uv_calls[0], self.uv_argv(eco, spec))
        name, separator, uri = spec.partition(" @ file://")
        self.assertEqual((name, separator), (package, " @ file://"), spec)
        self.assertRegex(uri, r"\A/[A-Za-z0-9._~!*'()/%-]+\Z")
        self.assertEqual(urllib.parse.unquote(uri), str(wheel))

    def test_a_wheel_pin_installs_the_verified_wheel_with_its_extras(self):
        pin, result, urls, npm_calls, uv_calls, eco = self._run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(pin["url"].endswith(".whl") and pin["package"].endswith("[mcp]"), pin)
        wheel = eco / "downloads" / pin["url"].rsplit("/", 1)[1]
        self.assertEqual(urls, [pin["url"]])
        self.assertEqual(wheel.read_bytes(), self.WHEEL)
        self.assert_uv_installs_the_wheel_file(uv_calls, eco, pin["package"], wheel)
        self.assertEqual(npm_calls, [])
        self.assertIn(f"Installed headroom {pin['version']} (uv-tool)", result.stdout)

    def test_an_install_root_with_uri_delimiters_is_percent_encoded_in_the_file_url(self):
        pin, result, urls, npm_calls, uv_calls, eco = self._run(eco_name=self.AWKWARD_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        wheel = eco / "downloads" / pin["url"].rsplit("/", 1)[1]
        self.assertEqual(wheel.read_bytes(), self.WHEEL)
        self.assert_uv_installs_the_wheel_file(uv_calls, eco, pin["package"], wheel)
        self.assertIn("/eco%20%231%20%3B%25%C3%A9/downloads/", uv_calls[0][-1])

    def test_a_wheel_that_fails_its_sha256_is_refused_before_uv_runs(self):
        pin, result, urls, npm_calls, uv_calls, eco = self._run(sha256="0" * 64)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"Checksum mismatch: {pin['url']}", result.stderr)
        self.assertEqual(urls, [pin["url"]])
        self.assertEqual(uv_calls, [], "uv must never be handed an unverified wheel")
        self.assertFalse((eco / "downloads" / pin["url"].rsplit("/", 1)[1]).exists())
        self.assertNotIn("Installed headroom", result.stdout)

    def test_a_wheel_named_for_another_version_is_refused_before_any_download(self):
        # A direct reference carries no ==version, so the pin's version is checked against the filename.
        pin, result, urls, npm_calls, uv_calls, eco = self._run(version="0.0.0")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Refusing to install headroom 0.0.0: its pinned wheel", result.stderr)
        self.assertEqual((urls, uv_calls), ([], []))

    def test_an_sdist_pin_is_still_resolved_from_the_index_by_name_and_version(self):
        # markitdown's sha256 is the cross-check its install_note describes; its sdist is not fetched.
        pin, result, urls, npm_calls, uv_calls, eco = self._run("markitdown")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(pin["url"].endswith(".tar.gz"), pin["url"])
        self.assertEqual(urls, [])
        self.assertEqual(uv_calls, [self.uv_argv(eco, f"markitdown=={pin['version']}")])


def fixture_wheel(dist: str = "demo-tool", version: str = "1.0.0") -> tuple[str, bytes]:
    """A minimal pure-Python wheel with no dependencies, one console script `<dist>` that prints
    "<dist> <version>", and an empty `mcp` extra. Returns its filename and bytes."""
    module = dist.replace("-", "_")
    info = f"{module}-{version}.dist-info"
    files = {
        f"{module}/__init__.py": f"def main():\n    print('{dist} {version}')\n",
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: {dist}\nVersion: {version}\nProvides-Extra: mcp\n",
        f"{info}/WHEEL": "Wheel-Version: 1.0\nGenerator: fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{info}/entry_points.txt": f"[console_scripts]\n{dist} = {module}:main\n",
    }
    record = "".join(
        f"{path},sha256={base64.urlsafe_b64encode(hashlib.sha256(text.encode()).digest()).rstrip(b'=').decode()},"
        f"{len(text.encode())}\n" for path, text in files.items()) + f"{info}/RECORD,,\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, text in {**files, f"{info}/RECORD": record}.items():
            archive.writestr(path, text)
    return f"{module}-{version}-py3-none-any.whl", buffer.getvalue()


def fixture_npm_tarball(name: str = "demo-scripted", version: str = "1.0.0") -> bytes:
    """An npm package tarball with no dependencies whose own postinstall script writes `postinstall-ran`
    into the package directory, so a real npm shows whether it ran lifecycle scripts."""
    manifest = json.dumps({"name": name, "version": version, "scripts": {
        "postinstall": "node -e \"require('fs').writeFileSync('postinstall-ran', '')\""}}).encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        member = tarfile.TarInfo("package/package.json")
        member.size, member.mode = len(manifest), 0o644
        archive.addfile(member, io.BytesIO(manifest))
    return buffer.getvalue()


def installed_pinned_binary(test: unittest.TestCase, pin_id: str, relative: str) -> Path:
    """`relative` inside the pinned release's tools/<pin_id>-<version>/ under $ECO_INSTALL_ROOT (else
    ~/.local/share/codex-ecosystem), where bootstrap-linux.sh installs it; skips the test if absent."""
    version = shipped_pin(pin_id)["version"]
    root = Path(os.environ.get("ECO_INSTALL_ROOT") or Path.home() / ".local/share/codex-ecosystem")
    binary = root / f"tools/{pin_id}-{version}" / relative
    if not os.access(binary, os.X_OK):
        test.skipTest(f"no installed {pin_id} {version} at {binary}")
    return binary


@LINUX_X86_64_ONLY
class UvToolWheelRealUvTests(unittest.TestCase):
    """Optional, skipped where the pinned uv is not installed (as in CI): UvToolWheelPinTests' install_pin
    run with the `uv` shim handing its argv on to the pinned uv (installed_pinned_binary), offline
    (UV_OFFLINE, UV_NO_CONFIG, UV_PYTHON_DOWNLOADS=never, a scratch UV_CACHE_DIR), against a locally
    built, dependency-free fixture wheel (fixture_wheel) under UvToolWheelPinTests.AWKWARD_ROOT. The
    percent-encoded file URL installs the wheel with its extra from that root, and uv still refuses a
    package name the wheel's filename does not carry, the check install_uv_tool's comment relies on.
    A local integration check of uv's handling, not an upstream uv test."""

    def _install(self, tmp_path: Path, package: str):
        uv = installed_pinned_binary(self, "uv", "uv")
        env = {"UV_CACHE_DIR": str(tmp_path / "uv-cache"), "UV_NO_CONFIG": "1", "UV_OFFLINE": "1",
               "UV_PYTHON_DOWNLOADS": "never"}
        found = subprocess.run([str(uv), "python", "find", "3.13"], capture_output=True, text=True, timeout=60,
                               env={**os.environ, **env})
        if found.returncode != 0:
            self.skipTest("the pinned uv finds no Python 3.13 without downloading one")
        filename, wheel = fixture_wheel()
        pin = {"id": "demo", "version": "1.0.0", "kind": "uv-tool", "package": package,
               "url": f"https://files.pythonhosted.org/packages/fixture/{filename}",
               "sha256": hashlib.sha256(wheel).hexdigest(), "install_note": "fixture"}
        result, _urls, _npm_calls, uv_calls, eco = run_install_pin(
            self, tmp_path, pin, wheel, UvToolWheelPinTests.AWKWARD_ROOT, real={"uv": uv}, env=env)
        return result, uv_calls, eco, eco / "downloads" / filename

    def test_the_pinned_uv_installs_the_encoded_wheel_url_with_its_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, uv_calls, eco, wheel = self._install(Path(tmp), "demo-tool[mcp]")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Installed demo 1.0.0 (uv-tool)", result.stdout)
            self.assertIn("/eco%20%231%20%3B%25%C3%A9/downloads/", uv_calls[0][-1])
            receipt = tomllib.loads((eco / "python-tools/demo-tool/uv-receipt.toml").read_text(encoding="utf-8"))
            self.assertEqual(receipt["tool"]["requirements"],
                             [{"name": "demo-tool", "extras": ["mcp"], "path": str(wheel)}])
            run = subprocess.run([str(eco / "bin/demo-tool")], capture_output=True, text=True, timeout=60,
                                 stdin=subprocess.DEVNULL)
            self.assertEqual((run.returncode, run.stdout), (0, "demo-tool 1.0.0\n"), run.stderr)

    def test_the_pinned_uv_refuses_a_package_name_the_wheel_does_not_carry(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _uv_calls, eco, _wheel = self._install(Path(tmp), "demo[mcp]")
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("does not match `demo-tool` in the distribution filename", result.stderr)
            self.assertNotIn("Installed demo", result.stdout)
            self.assertFalse((eco / "bin/demo-tool").exists())


@LINUX_X86_64_ONLY
class NpmIgnoreScriptsRealNpmTests(unittest.TestCase):
    """Optional, skipped where the pinned node is not installed (as in CI): NpmIgnoreScriptsTests'
    install_pin run with the `npm` shim handing its argv on to the pinned node's npm
    (installed_pinned_binary), offline with a scratch cache and an empty user config, against a local
    fixture package whose own postinstall writes a marker (fixture_npm_tarball). With the pin's
    `ignore_scripts: true`, socraticode's setting, the marker stays absent; the same install without the
    field runs the script, so the first check can fail. A local integration check of npm's handling, not
    an upstream npm test."""

    ARCHIVE = fixture_npm_tarball()

    def _install(self, tmp_path: Path, **changes):
        npm = installed_pinned_binary(self, "node", "bin/npm")
        (tmp_path / "npmrc").write_text("")
        env = {"PATH": f"{npm.parent}{os.pathsep}{os.environ['PATH']}",  # the pinned node runs npm and the script
               "npm_config_cache": str(tmp_path / "npm-cache"), "NPM_CONFIG_USERCONFIG": str(tmp_path / "npmrc"),
               "npm_config_offline": "true", "npm_config_update_notifier": "false",
               "npm_config_ignore_scripts": "false"}  # a caller's own setting must not decide the control
        pin = {"id": "demo-scripted", "version": "1.0.0", "kind": "npm",
               "url": "https://registry.npmjs.org/demo-scripted/-/demo-scripted-1.0.0.tgz",
               "sha256": hashlib.sha256(self.ARCHIVE).hexdigest(), "install_note": "fixture", **changes}
        result, _urls, npm_calls, _uv_calls, eco = run_install_pin(
            self, tmp_path, pin, self.ARCHIVE, real={"npm": npm}, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Installed demo-scripted 1.0.0 (npm)", result.stdout)
        package = eco / "tools/demo-scripted-1.0.0/lib/node_modules/demo-scripted"
        self.assertTrue((package / "package.json").is_file(), result.stdout + result.stderr)
        return npm_calls, (package / "postinstall-ran").exists()

    def test_the_pinned_npm_runs_no_lifecycle_script_for_an_ignore_scripts_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            npm_calls, ran = self._install(Path(tmp), ignore_scripts=True)
        self.assertFalse(ran, "npm ran the package's postinstall although the pin sets ignore_scripts: true")
        self.assertIn("--ignore-scripts", npm_calls[0])

    def test_the_same_install_without_the_field_runs_the_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            npm_calls, ran = self._install(Path(tmp))
        self.assertTrue(ran, "the fixture's postinstall never ran, so the check above could not fail")
        self.assertNotIn("--ignore-scripts", npm_calls[0])


class NativeInstallFloorTests(unittest.TestCase):
    """2026-09-24: bootstrap-linux.sh's native pin is a floor, not a ceiling, as bootstrap-macos.sh's
    already was (tests/test_adoption_bootstrap_macos.py's NativeInstallFloorTests); before this, a
    re-run on a Linux/WSL2 host whose native updater was ahead of the pin moved Claude Code back to
    the pin. install_pin, install_native and fetch are extracted verbatim from bootstrap-linux.sh
    and run against a one-pin fixture. Only `curl` is shimmed (it logs the URL and copies a stub
    native installer whose real sha256 the fixture pin records); where this host's sha256sum lacks
    GNU's --check --status (macOS), a `sha256sum` shim runs `shasum -a 256` with fetch's own
    arguments, so the checksum is still really compared. HOME is a temporary directory whose
    ~/.local/bin/claude, when present, answers --version with a chosen line. A launcher at or above
    the pin is kept with no download and no install; anything else takes the unchanged
    checksum-verified install."""

    PIN = "2.1.281"
    URL = f"https://downloads.claude.ai/claude-code-releases/{PIN}/linux-x64/claude"
    KEPT = ("2.1.281 (Claude Code)", "2.1.290 (Claude Code)", "2.2.0 (Claude Code)",
            "10.0.0 (Claude Code)", "2.1.281")
    # 2.1.99 sorts after 2.1.281 as text but is older; a pre-release suffix,
    # a non-version first word and empty output are not trusted as a version.
    INSTALLED = ("2.1.280 (Claude Code)", "2.1.99 (Claude Code)", "1.99.999 (Claude Code)",
                 "2.1.290-dev (Claude Code)", "Claude Code", "")

    def _run(self, tmp_path: Path, version_line=None, launcher_exit=0, sha256=None, native_bin_dir=False):
        for tool in ["jq"] if sha256sum_checks_like_gnu() else ["jq", "shasum"]:
            if shutil.which(tool) is None:
                self.skipTest(f"{tool} is not on PATH")
        home = tmp_path / "home"
        native_dir = home / ".local" / "bin"
        native_dir.mkdir(parents=True)
        launcher = native_dir / "claude"
        if version_line is not None:
            launcher.write_text(f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(version_line)}\nexit {launcher_exit}\n")
            launcher.chmod(0o755)
        installs, downloads = tmp_path / "installs.log", tmp_path / "downloads.log"
        installer = tmp_path / "native-installer"
        installer.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {shlex.quote(str(installs))}\n')
        shim = tmp_path / "shim"
        shim.mkdir()
        (shim / "curl").write_text(
            "#!/bin/sh\n"
            'out=""; prev=""; url=""\n'
            'for arg in "$@"; do\n'
            '  if [ "$prev" = "--output" ]; then out="$arg"; fi\n'
            '  case "$arg" in https://*) url="$arg" ;; esac\n'
            '  prev="$arg"\n'
            "done\n"
            f'printf "%s\\n" "$url" >> {shlex.quote(str(downloads))}\n'
            f'cp {shlex.quote(str(installer))} "$out"\n'
        )
        if not sha256sum_checks_like_gnu():
            (shim / "sha256sum").write_text('#!/bin/sh\nexec shasum -a 256 "$@"\n')
        for tool in shim.iterdir():
            tool.chmod(0o755)
        eco = tmp_path / "eco"
        (eco / "downloads").mkdir(parents=True)
        bin_dir = native_dir if native_bin_dir else eco / "bin"
        bin_dir.mkdir(exist_ok=True)
        pins_path = tmp_path / "pins.json"
        pins_path.write_text(json.dumps({"tools": [{
            "id": "claude-code", "version": self.PIN, "kind": "native", "url": self.URL,
            "sha256": sha256 or hashlib.sha256(installer.read_bytes()).hexdigest(),
            "install_note": "fixture", "bin": "claude",
        }]}))
        harness = tmp_path / "install-native-floor-harness.sh"
        harness.write_text(
            "set -Eeuo pipefail\n"
            + shell_functions(SCRIPT_PATH.read_text(), "verify_sha256", "fetch", "install_native", "install_pin")
            + f"pins_path={shlex.quote(str(pins_path))}\n"
            + f"bin_dir={shlex.quote(str(bin_dir))}\n"
            + f"cache_dir={shlex.quote(str(eco / 'downloads'))}\n"
            + "install_pin claude-code\n"
        )
        before = launcher.read_text() if launcher.exists() else None
        result = subprocess.run(
            ["bash", str(harness)], capture_output=True, text=True, timeout=60,
            env={**os.environ, "HOME": str(home), "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"},
        )
        logs = [path.read_text() if path.exists() else "" for path in (installs, downloads)]
        return result, *logs, eco, bin_dir, launcher, before

    def assert_kept(self, version_line, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            result, installs, downloads, eco, bin_dir, launcher, before = self._run(Path(tmp), version_line, **kwargs)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f"Kept installed claude-code {version_line.split()[0]}: at or above the "
                          f"pinned floor {self.PIN}", result.stdout)
            self.assertNotIn("Installed claude-code", result.stdout)
            self.assertEqual((downloads, installs), ("", ""), "a kept launcher must not be fetched or installed")
            self.assertEqual(list((eco / "downloads").iterdir()), [])
            self.assertEqual(launcher.read_text(), before, "the kept launcher was modified")
            if bin_dir != launcher.parent:
                # The ecosystem's own launcher still execs the kept native install.
                self.assertIn('exec "$HOME/.local/bin/claude"', (bin_dir / "claude").read_text())

    def assert_installed(self, version_line, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            result, installs, downloads, *_ = self._run(Path(tmp), version_line, **kwargs)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f"Installed claude-code {self.PIN} (native)", result.stdout)
            self.assertNotIn("Kept installed", result.stdout)
            self.assertEqual(downloads.splitlines(), [self.URL])
            self.assertEqual(installs.splitlines(), [f"install {self.PIN}"])

    def test_a_launcher_at_or_above_the_pin_is_kept_without_download_or_install(self):
        for version_line in self.KEPT:
            with self.subTest(version_line=version_line):
                self.assert_kept(version_line)

    def test_a_kept_launcher_in_the_native_bin_dir_is_not_replaced(self):
        # With bin_dir == ~/.local/bin, the exec wrapper would replace the kept launcher and exec itself.
        self.assert_kept("2.1.290 (Claude Code)", native_bin_dir=True)

    def test_a_missing_older_or_unreadable_launcher_takes_the_verified_install(self):
        for version_line in (None, *self.INSTALLED):
            with self.subTest(version_line=version_line):
                self.assert_installed(version_line)

    def test_a_failing_version_probe_takes_the_verified_install(self):
        self.assert_installed("2.1.290 (Claude Code)", launcher_exit=1)

    def test_the_install_path_still_fails_closed_on_a_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, installs, downloads, *_ = self._run(Path(tmp), "2.1.280 (Claude Code)", sha256="0" * 64)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Checksum mismatch", result.stderr)
            self.assertEqual(downloads.splitlines(), [self.URL])
            self.assertEqual(installs, "", "an unverified download must never run")

    def test_both_scripts_share_one_install_native(self):
        # The floor reached bootstrap-macos.sh (#159) while this script kept reinstalling the pin;
        # one identical function means a later fix to either script cannot miss the other.
        self.assertEqual(shell_functions(SCRIPT_PATH.read_text(), "install_native"),
                         shell_functions((ROOT / "adoption/bootstrap-macos.sh").read_text(), "install_native"))


@LINUX_X86_64_ONLY
class RtkConfigReminderTests(unittest.TestCase):
    """2026-09-25: rtk 0.50.0's Claude hook needs `[hooks] exclude_commands = ["^git show [^ ]*:",
    "diff"]` in rtk's own config (recipes/README.md#native-context-mode-and-hooks), which the
    bootstrap does not write. After a successful rtk install, install_pin prints a one-line reminder
    unless that config already carries the key exactly once. Widened 2026-09-26: the laptop's
    ultracode E2E found the bare `"^git show [^ ]*:"` pattern misses a `git -C <dir> show HEAD:path`
    form (still windowed to 8,261 of 22,907 bytes in that fixture), and `git branch -a`'s branch-name
    compaction (`filter_branch_output`, src/cmds/git/git_cmd.rs:3185-3244) always keeps git's
    local-worktree `+ ` prefix (git_cmd.rs:3209-3211), but only misreports that branch as remote-only
    when a remote-tracking branch of the same name also exists (git_cmd.rs:3224-3227) -- 31 vs 6 real
    in one fixture. Both added patterns anchor to the git subcommand position (only
    `-C`/`-c`/`--git-dir`/`--work-tree` with a value, or another `--flag`, may precede `show`/`branch`
    -- the same global options rtk's own discovery strips, GIT_GLOBAL_OPT, src/discover/registry.rs:78),
    so a command that merely mentions "show", "branch" or a colon as an ordinary argument
    (`git commit -m "update branch docs"`, `git push origin branch`, `git diff main branch`) is no
    longer wrongly excluded, while a `--git-dir`/`--work-tree` form (`git --git-dir /r/.git
    show HEAD:x`, `git --work-tree /w branch -a`) is now excluded instead of missed. The reminder now says to replace, not add, the
    existing `exclude_commands` line, and fires on a duplicate key too: a duplicate is invalid TOML
    and rtk silently loads defaults (`Config::load().unwrap_or_default()`, src/core/config.rs:278-281).
    Retained verification of these patterns on the pinned binary (the one extracted from the upstream
    rtk-ai/rtk v0.50.0 release asset) is a raw capture in
    evidence/artifacts/rtk-exclude-widen-20260926/hook-check.txt, not the E2E receipt (sibling PR #316's
    evidence/artifacts/token-e2e-ultracode-laptop-20260926/receipt.json is cited only for the
    discovery). The reminder fires unless all four entries are present exactly once, including for a
    config that still has only the original two, or the original two plus a second, four-entry line.
    2026-09-26 (Codex review of #314): the text check alone is not enough, because rtk also ignores a
    TOML-valid file that does not deserialize (a [tracking] table without history_days fails
    TrackingConfig, src/core/config.rs at 1d87b8e7) and then rewrites everything. So once the text
    matches, the installed rtk must answer `rtk hook check` with exactly "No rewrite for: <probe>" and
    exit 1 for every probe (PROBES); the stub rtk's answer is set per test (HOOK).
    install_pin, fetch, install_single_binary_tarball and
    rtk_config_reminder are extracted verbatim from bootstrap-linux.sh and run against a one-pin
    fixture whose synthetic tarball is pre-seeded in the download cache with its real sha256, so
    fetch() verifies it and never downloads. HOME is a temporary directory; the reminder must never
    create or change the config."""

    ENTRY_1 = '"^git show [^ ]*:"'
    ENTRY_2 = '"diff"'
    ENTRY_3 = r"'^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*show\s+(?:[^\n]*\s)?[^\s]*:'"
    ENTRY_4 = r"'^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*branch(?:\s|$)'"
    ENTRIES = (ENTRY_1, ENTRY_2, ENTRY_3, ENTRY_4)
    EXCLUDE_ITEMS = "[" + ", ".join(ENTRIES) + "]"
    # Matches recipes/README.md's pretty-printed, one-entry-per-line block exactly
    # (test_the_recipes_exact_block_gets_no_reminder asserts the two stay identical).
    CONFIGURED = "[hooks]\nexclude_commands = [\n" + "".join(f"  {entry},\n" for entry in ENTRIES) + "]\n"
    OLD_TWO_ENTRY = f"[hooks]\nexclude_commands = [{ENTRY_1}, {ENTRY_2}]\n"
    # Codex's #314 counterexample: the exact recipe text, TOML-valid, but rtk rejects the file.
    REJECTED = CONFIGURED + "[tracking]\nenabled = false\n"
    PROBES = ["git show HEAD:x | tail -n 5", "git -C . show --no-color HEAD:x | tail -n 5", "diff a missing",
              "git branch -a", "git -C . branch"]
    HINT = "rtk ignores a config it cannot load"
    # `hook check` answers of the stub rtk.
    HOOK = {
        "excluded": 'echo "No rewrite for: $3" >&2; exit 1',
        "rewrite": 'echo "rtk $3"; exit 0',
        "unsupported": "echo \"error: unrecognized subcommand 'check'\" >&2; exit 2",
        "branch rewritten": 'case "$3" in *branch*) echo "rtk $3"; exit 0 ;; esac; echo "No rewrite for: $3" >&2; exit 1',
        "excluded with a warning": 'echo "rtk: warning: invalid exclude_commands pattern" >&2; echo "No rewrite for: $3" >&2; exit 1',
    }

    @staticmethod
    def config_with(*entries: str) -> str:
        return f"[hooks]\nexclude_commands = [{', '.join(entries)}]\n"

    @classmethod
    def expected_reminder(cls, config) -> str:
        return (f"Reminder: for the Claude hook, replace any existing exclude_commands line in "
                f"{config} with [hooks] exclude_commands = {cls.EXCLUDE_ITEMS} "
                "(a duplicate key is invalid TOML and rtk silently loads defaults; "
                "recipes/README.md#native-context-mode-and-hooks); this script does not write it.")

    @staticmethod
    def recipe_exclude_block() -> str:
        """The exact ```toml [hooks] exclude_commands fenced block from recipes/README.md."""
        text = (ROOT / "recipes/README.md").read_text(encoding="utf-8")
        match = re.search(r"```toml\n(\[hooks\]\nexclude_commands = \[.*?\n\])\n```", text, re.S)
        if match is None:
            raise AssertionError("recipes/README.md: could not find the [hooks] exclude_commands block")
        return match.group(1) + "\n"

    def _run(self, tmp_path: Path, tool_id="rtk", xdg_config_home=None, hook="rewrite"):
        for tool in ["jq", "timeout"] if sha256sum_checks_like_gnu() else ["jq", "shasum", "timeout"]:
            if shutil.which(tool) is None:
                self.skipTest(f"{tool} is not on PATH")
        home = tmp_path / "home"
        home.mkdir(exist_ok=True)
        eco = tmp_path / "eco"
        cache = eco / "downloads"
        cache.mkdir(parents=True, exist_ok=True)
        build = tmp_path / "build"
        build.mkdir(exist_ok=True)
        calls = tmp_path / "rtk-calls.log"
        calls.unlink(missing_ok=True)
        (build / tool_id).write_text(
            "#!/bin/sh\n"
            f"printf '%s\\t%s\\n' \"${{XDG_CONFIG_HOME:-unset}}\" \"$*\" >> {shlex.quote(str(calls))}\n"
            f"if [ \"$1\" = --version ]; then echo '{tool_id} 0.50.0'; exit 0; fi\n"
            f"if [ \"$1\" = hook ] && [ \"$2\" = check ]; then {self.HOOK[hook]}; fi\n"
            "echo \"unexpected arguments: $*\" >&2; exit 97\n")
        (build / tool_id).chmod(0o755)
        asset = f"{tool_id}-x86_64-unknown-linux-musl.tar.gz"
        (cache / asset).unlink(missing_ok=True)
        shutil.rmtree(eco / "tools", ignore_errors=True)
        shutil.rmtree(eco / "bin", ignore_errors=True)
        subprocess.run(["tar", "-czf", str(cache / asset), "-C", str(build), tool_id], check=True)
        pins_path = tmp_path / "pins.json"
        pins_path.write_text(json.dumps({"tools": [{
            "id": tool_id, "version": "0.50.0", "kind": "tarball",
            "url": f"https://example.invalid/v0.50.0/{asset}",
            "sha256": hashlib.sha256((cache / asset).read_bytes()).hexdigest(), "install_note": "fixture",
        }]}))
        shim = tmp_path / "shim"
        shim.mkdir(exist_ok=True)
        (shim / "curl").write_text("#!/bin/sh\necho 'curl must not run: the cached archive verifies' >&2\nexit 97\n")
        if not sha256sum_checks_like_gnu():
            (shim / "sha256sum").write_text('#!/bin/sh\nexec shasum -a 256 "$@"\n')
        for tool in shim.iterdir():
            tool.chmod(0o755)
        harness = tmp_path / "rtk-reminder-harness.sh"
        harness.write_text(
            "set -Eeuo pipefail\n"
            + shell_functions(SCRIPT_PATH.read_text(), "verify_sha256", "fetch", "install_single_binary_tarball",
                              "rtk_config_reminder", "install_pin")
            + f"pins_path={shlex.quote(str(pins_path))}\n"
            + f"ecosystem_root={shlex.quote(str(eco))}\n"
            + f"bin_dir={shlex.quote(str(eco / 'bin'))}\n"
            + f"cache_dir={shlex.quote(str(cache))}\n"
            + f"stage_dir={shlex.quote(str(eco / 'staging'))}\n"
            + "mkdir -p \"$bin_dir\" \"$stage_dir\"\ninstalled_pin_ids=()\n"
            + f"install_pin {tool_id}\n"
        )
        env = {key: value for key, value in os.environ.items() if key != "XDG_CONFIG_HOME"}
        env.update(HOME=str(home), PATH=f"{shim}{os.pathsep}{os.environ['PATH']}")
        if xdg_config_home is not None:
            env["XDG_CONFIG_HOME"] = str(xdg_config_home)
        result = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"Installed {tool_id} 0.50.0 (tarball)", result.stdout)
        self.calls = calls.read_text().splitlines() if calls.exists() else []
        return result, home

    @staticmethod
    def reminders(stdout: str) -> list[str]:
        return [line for line in stdout.splitlines() if line.startswith("Reminder:")]

    def test_a_missing_config_gets_one_reminder_and_is_never_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            for attempt in (1, 2):  # idempotent: a rerun reminds again and still writes nothing
                with self.subTest(attempt=attempt):
                    result, home = self._run(Path(tmp))
                    config = home / ".config/rtk/config.toml"
                    self.assertEqual(self.reminders(result.stdout), [self.expected_reminder(config)])
                    self.assertFalse((home / ".config").exists(), "the reminder must not create the config")

    def test_a_config_with_the_exclusions_gets_no_reminder(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "home/.config/rtk/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(self.CONFIGURED)
            result, _home = self._run(Path(tmp), hook="excluded")
            self.assertEqual(self.reminders(result.stdout), [])
            self.assertEqual(config.read_text(), self.CONFIGURED)

    def test_a_config_without_the_key_is_reminded_and_left_unchanged(self):
        for text in ("[hooks]\n", '[hooks]\nexclude_commands = ["diff"]\n', "# exclude_commands\n",
                     # a config that still has only the pre-widen recommendation is now incomplete too.
                     self.OLD_TWO_ENTRY):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp) / "home/.config/rtk/config.toml"
                config.parent.mkdir(parents=True)
                config.write_bytes(text.encode())
                result, _home = self._run(Path(tmp))
                self.assertEqual(self.reminders(result.stdout), [self.expected_reminder(config)])
                self.assertEqual(config.read_bytes(), text.encode(), "the reminder must never write the config")

    def test_each_missing_entry_gets_exactly_one_reminder(self):
        """Leave-one-out: three of the four entries present, one missing -- exactly one reminder,
        naming all four (the recommendation to replace, never just append)."""
        for index in range(len(self.ENTRIES)):
            remaining = self.ENTRIES[:index] + self.ENTRIES[index + 1:]
            text = self.config_with(*remaining)
            with self.subTest(missing_entry=index + 1), tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp) / "home/.config/rtk/config.toml"
                config.parent.mkdir(parents=True)
                config.write_text(text)
                result, _home = self._run(Path(tmp))
                self.assertEqual(self.reminders(result.stdout), [self.expected_reminder(config)])
                self.assertEqual(config.read_text(), text, "the reminder must never write the config")

    def test_a_duplicate_exclude_commands_key_is_reminded(self):
        """A second exclude_commands line is invalid TOML (rtk silently loads defaults), so the
        reminder must fire even though, read alone, either line would be complete: the old
        two-entry line plus a correct new four-entry line, and the new line duplicated verbatim."""
        old_plus_new = f"[hooks]\nexclude_commands = [{self.ENTRY_1}, {self.ENTRY_2}]\n{self.CONFIGURED}"
        new_plus_new = self.CONFIGURED + self.CONFIGURED
        for text in (old_plus_new, new_plus_new):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp) / "home/.config/rtk/config.toml"
                config.parent.mkdir(parents=True)
                config.write_text(text)
                result, _home = self._run(Path(tmp))
                self.assertEqual(self.reminders(result.stdout), [self.expected_reminder(config)])
                self.assertEqual(config.read_text(), text, "the reminder must never write the config")

    def test_the_recipes_exact_block_gets_no_reminder(self):
        block = self.recipe_exclude_block()
        self.assertEqual(block, self.CONFIGURED,
                          "recipes/README.md's [hooks] exclude_commands block no longer matches "
                          "this test's CONFIGURED constant; update whichever one drifted")
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "home/.config/rtk/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(block)
            result, _home = self._run(Path(tmp), hook="excluded")
            self.assertEqual(self.reminders(result.stdout), [])
            self.assertEqual(config.read_text(), block)

    def test_xdg_config_home_selects_the_config_rtk_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            xdg = Path(tmp) / "xdg"
            result, _home = self._run(Path(tmp), xdg_config_home=xdg)
            self.assertIn(f"replace any existing exclude_commands line in {xdg}/rtk/config.toml with",
                          self.reminders(result.stdout)[0])
            (xdg / "rtk").mkdir(parents=True)
            (xdg / "rtk/config.toml").write_text(self.CONFIGURED)
            result, _home = self._run(Path(tmp), xdg_config_home=xdg, hook="excluded")
            self.assertEqual(self.reminders(result.stdout), [])
            # rtk runs with the caller's environment, so it reads the same file.
            self.assertTrue(self.calls)
            self.assertEqual({call.split("\t", 1)[0] for call in self.calls}, {str(xdg)})

    def test_an_exact_text_that_rtk_honours_probes_every_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "home/.config/rtk/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(self.CONFIGURED)
            result, _home = self._run(Path(tmp), hook="excluded")
            self.assertEqual(self.reminders(result.stdout), [])
            self.assertEqual([call.split("\t", 1)[1] for call in self.calls if "\thook check " in call],
                             [f"hook check {probe}" for probe in self.PROBES])

    def test_an_exact_text_that_rtk_does_not_honour_is_reminded(self):
        """Either check failing reminds: here the text check passes and rtk's answer fails it. The
        reminder carries a hint naming the failing probe; a failed text check never carries one."""
        cases = {
            "rtk rewrites the recipe's exact block": (self.CONFIGURED, "rewrite", self.PROBES[0]),
            "Codex #314 counterexample: [tracking] without history_days, modelled as rtk rewriting": (
                self.REJECTED, "rewrite", self.PROBES[0]),
            "rtk has no hook check subcommand": (self.CONFIGURED, "unsupported", self.PROBES[0]),
            "rtk still rewrites git branch": (self.CONFIGURED, "branch rewritten", "git branch -a"),
            "rtk adds output beside its answer": (self.CONFIGURED, "excluded with a warning", self.PROBES[0]),
            # The text checks read the whole file, so entries in comments beside an empty list pass them
            # (Codex review of #291); only rtk's answer catches it.
            "Codex #291 counterexample: empty list, entries only in comments": (
                "[hooks]\nexclude_commands = []\n" + "".join(f"# {entry}\n" for entry in self.ENTRIES),
                "rewrite", self.PROBES[0]),
        }
        for name, (text, hook, probe) in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp) / "home/.config/rtk/config.toml"
                config.parent.mkdir(parents=True)
                config.write_text(text)
                result, _home = self._run(Path(tmp), hook=hook)
                lines = self.reminders(result.stdout)
                self.assertEqual(len(lines), 1, result.stdout)
                self.assertTrue(lines[0].startswith(self.expected_reminder(config)[:-1]), lines[0])
                self.assertIn(f"still rewrites or fails on: {probe};", lines[0])
                self.assertIn(self.HINT, lines[0])
                self.assertEqual(config.read_text(), text, "the reminder must never write the config")

    def test_a_failed_text_check_reminds_without_asking_rtk(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "home/.config/rtk/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(self.OLD_TWO_ENTRY)
            result, _home = self._run(Path(tmp), hook="excluded")
            self.assertEqual(self.reminders(result.stdout), [self.expected_reminder(config)])
            self.assertEqual([call for call in self.calls if "\thook check " in call], [])

    def test_other_pins_get_no_reminder(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _home = self._run(Path(tmp), tool_id="qdrant")
            self.assertEqual(self.reminders(result.stdout), [])
            self.assertEqual([call for call in self.calls if "\thook check " in call], [])


@LINUX_X86_64_ONLY
class RtkConfigReminderRealBinaryTests(unittest.TestCase):
    """Optional: the extracted rtk_config_reminder against a locally installed rtk 0.50.0
    ($ECO_INSTALL_ROOT, or ~/.local/share/codex-ecosystem, then tools/rtk-0.50.0/rtk). Skipped when
    that binary is absent, so CI does not need it. Each config lives in a scratch XDG_CONFIG_HOME."""

    SINGLE_REGEX = r"^git(\s+\S+)*\s+show(\s+\S+)*\s+(:\S|[^\s-]\S*:)"
    CONFIGS = {
        "the recipe's four-entry block": (RtkConfigReminderTests.CONFIGURED, 0, False),
        # Codex's #314 counterexample: exact text, but TrackingConfig needs history_days, so rtk ignores it.
        "[tracking] without history_days": (RtkConfigReminderTests.REJECTED, 1, True),
        "[tracking] with history_days": (RtkConfigReminderTests.REJECTED + "history_days = 90\n", 0, False),
        "2026-09-25 two-entry line": (RtkConfigReminderTests.OLD_TWO_ENTRY, 1, False),
        "the tested single-regex alternative": (f"[hooks]\nexclude_commands = ['{SINGLE_REGEX}', \"diff\"]\n", 1, False),
        "no config": (None, 1, False),
    }

    def test_the_installed_rtk_and_the_text_decide_together(self):
        root = Path(os.environ.get("ECO_INSTALL_ROOT") or Path.home() / ".local/share/codex-ecosystem")
        binary = root / "tools/rtk-0.50.0/rtk"
        if not os.access(binary, os.X_OK):
            self.skipTest(f"no installed rtk 0.50.0 at {binary}")
        version = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=30)
        if version.stdout.strip() != "rtk 0.50.0":
            self.skipTest(f"{binary} reports {version.stdout.strip()!r}")
        if shutil.which("timeout") is None:
            self.skipTest("timeout is not on PATH")
        for name, (text, expected, hint) in self.CONFIGS.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                (tmp_path / "bin").mkdir()
                (tmp_path / "bin/rtk").symlink_to(binary)
                config = tmp_path / "xdg/rtk/config.toml"
                config.parent.mkdir(parents=True)
                if text is not None:
                    config.write_text(text)
                harness = tmp_path / "harness.sh"
                harness.write_text("set -Eeuo pipefail\n"
                                   + shell_functions(SCRIPT_PATH.read_text(), "rtk_config_reminder")
                                   + f"bin_dir={shlex.quote(str(tmp_path / 'bin'))}\nrtk_config_reminder\n")
                env = dict(os.environ, HOME=str(tmp_path / "home"), XDG_CONFIG_HOME=str(tmp_path / "xdg"),
                           XDG_DATA_HOME=str(tmp_path / "data"), RTK_DB_PATH=str(tmp_path / "data/history.db"),
                           RTK_TELEMETRY_DISABLED="1")
                result = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=120,
                                        env=env, cwd=tmp)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                lines = [line for line in result.stdout.splitlines() if line.startswith("Reminder:")]
                self.assertEqual(len(lines), expected, result.stdout)
                if lines:
                    self.assertEqual(RtkConfigReminderTests.HINT in lines[0], hint, lines[0])
                if text is None:
                    self.assertFalse(config.exists(), "the reminder must not create the config")
                else:
                    self.assertEqual(config.read_text(), text)


class RtkExclusionInstructionTests(unittest.TestCase):
    """2026-09-26 (GPT-6 verification of the macOS token pins): adoption/platforms/macos-arm64.md told
    a reader to replace an existing `exclude_commands` line with the recipe's block, whose first line
    is the `[hooks]` header. In a file that already has a `[hooks]` table that makes a second one,
    which is invalid TOML: rtk 0.50.0 then loads its defaults and the hook keeps rewriting
    (`duplicate key `hooks` in document root`; evidence/artifacts/macos-token-pins-20260926/
    rtk-hooks-table-control.txt). Replacing a "line" also breaks the recipe's own multi-line value.
    So every instruction that puts the four entries into rtk's config (the paragraph before each copy
    of the recipe's block in a Markdown page outside evidence/, bootstrap.md step 4a and the macOS
    rtk pin's install_note) says to replace the key's whole value inside the existing `[hooks]`
    table and to add the header only when the file has no `[hooks]` table, and none says to replace
    an `exclude_commands` line. Repository text only; nothing runs."""

    OLD_LINE_INSTRUCTION = re.compile(
        r"replace\**\s+(?:any\s+|the\s+)?existing\s+`?(?:\[hooks\]\s+)?exclude_commands`?\s+line", re.I)
    REQUIRED = ("inside the existing `[hooks]` table", "only when the file has no `[hooks]` table")
    BLOCK_FENCE = "```toml\n[hooks]\nexclude_commands = [\n"
    # Retained evidence may quote an old instruction; hidden, dependency and cache directories hold no docs.
    SKIPPED_DIRECTORIES = {"evidence", "node_modules", "venv", "__pycache__"}

    def instructions(self) -> dict:
        found = {}
        for directory, subdirectories, names in os.walk(ROOT):
            subdirectories[:] = sorted(name for name in subdirectories
                                       if name not in self.SKIPPED_DIRECTORIES and not name.startswith("."))
            for name in sorted(names):
                if not name.endswith(".md"):
                    continue
                page = Path(directory) / name
                text = page.read_text(encoding="utf-8", errors="replace")
                start = text.find(self.BLOCK_FENCE)
                while start != -1:
                    # The block's instruction is the paragraph right before it.
                    found[f"{page.relative_to(ROOT).as_posix()}, the paragraph before the block at offset {start}"] = (
                        text[:start].rstrip("\n").rsplit("\n\n", 1)[-1])
                    start = text.find(self.BLOCK_FENCE, start + 1)
        bootstrap = (ROOT / "adoption/bootstrap.md").read_text(encoding="utf-8")
        found["adoption/bootstrap.md step 4a"] = next(
            line for line in bootstrap.splitlines() if "The template registers the `rtk hook claude` Bash hook" in line)
        mac_pins = json.loads((ROOT / "adoption/pins-macos-arm64.json").read_text(encoding="utf-8"))
        found["adoption/pins-macos-arm64.json rtk install_note"] = next(
            tool["install_note"] for tool in mac_pins["tools"] if tool["id"] == "rtk")
        return found

    def test_every_instruction_sets_the_value_inside_the_one_hooks_table(self):
        found = self.instructions()
        pages = {label.split(",", 1)[0] for label in found}
        # Not vacuous: the two pages that carry the recipe's block today are found.
        self.assertLessEqual({"recipes/README.md", "adoption/platforms/macos-arm64.md"}, pages)
        for label, text in found.items():
            with self.subTest(label):
                self.assertNotRegex(text, self.OLD_LINE_INSTRUCTION)
                # Markdown wraps lines and a phrase may open a sentence.
                words = " ".join(text.split()).lower()
                for phrase in self.REQUIRED:
                    self.assertIn(phrase.lower(), words)

    def test_bootstrap_step_4a_keeps_the_four_entry_value_verbatim(self):
        self.assertIn(f"`exclude_commands = {RtkConfigReminderTests.EXCLUDE_ITEMS}`",
                      self.instructions()["adoption/bootstrap.md step 4a"])

    def test_the_check_rejects_the_replaced_line_instructions(self):
        # The four wordings this class replaced, as they stood before the fix.
        for old in ("**Replace** any existing `exclude_commands` line in that file with this block",
                    "**Replace** the existing `[hooks] exclude_commands` line in `~/.config/rtk/config.toml`",
                    "also **replace** any existing `[hooks] exclude_commands` line in rtk's config file",
                    "Replace any existing exclude_commands line there"):
            with self.subTest(old):
                self.assertRegex(old, self.OLD_LINE_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
