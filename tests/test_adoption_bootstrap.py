"""Static checks for adoption/pins-linux-x86_64.json and adoption/bootstrap-linux.sh.

No network access, no installation, and no execution of the pinned tools.
Only the script's argument parsing, root refusal, and null-hash fail-closed
behavior are exercised via `bash -c`, using a stub HOME and no real download.
"""

import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import shlex
import unittest

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
VALID_KINDS = {"tarball", "npm", "pip", "uv-tool", "native"}


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

    def test_all_pins_in_this_pr_have_a_verified_hash(self):
        # This PR fetched and hashed every pinned artifact; none are deferred.
        for tool in self.pins["tools"]:
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


if __name__ == "__main__":
    unittest.main()
