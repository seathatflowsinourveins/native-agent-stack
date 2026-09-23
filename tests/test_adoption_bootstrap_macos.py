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
# Every macos-arm64-foundation component now has a pin (socraticode's npm pin
# closed the last gap); documented_unpinned_ids in the script is empty and
# this set stays empty as the corresponding test-side mechanism, so a future
# undocumented gap is still caught instead of silently reusing a stale list.
DOCUMENTED_SKIPS = set()
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


# Everything the script looks for with `command -v` before it reads the pins.
PREREQUISITES = ("curl", "git", "tar", "shasum", "unzip", "jq", "mktemp")


def prerequisite_shim(directory: Path, omit=()) -> Path:
    """macos_shim plus real symlinks for the prerequisites, minus `omit`.

    The exit-4 test restricts PATH to exactly this directory, so anything not
    linked here is genuinely absent from the script's point of view without
    touching the host's own PATH. `dirname` is linked too: the script resolves
    its own directory with it before any check runs.
    """
    shim = macos_shim(directory)
    for tool in (*PREREQUISITES, "dirname", "basename"):
        if tool in omit:
            continue
        found = shutil.which(tool)
        if found:
            (shim / tool).symlink_to(found)
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

    def test_mcporter_note_does_not_claim_its_tarball_is_the_whole_install(self):
        # `npm view mcporter@0.13.13 dependencies bundleDependencies` (2026-09-22):
        # ten registry-resolved runtime dependencies, none bundled; rolldown@1.2.8
        # in turn selects a native darwin-arm64 binding.
        note = {tool["id"]: tool for tool in self.pins["tools"]}["mcporter"]["install_note"]
        self.assertNotIn("whole install", note)
        self.assertIn("UNPINNED", note)
        self.assertIn("rolldown", note)
        self.assertIn("@rolldown/binding-darwin-arm64", note)


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
        smoke = row["hosted_smoke"]
        self.assertEqual(smoke["workflow"], ".github/workflows/adoption-bootstrap.yml")
        self.assertEqual(smoke["job"], "bootstrap-macos")
        # A hosted run is native operation on a GitHub runner, never an
        # acceptance: the status may advance from pending to green, and no
        # value of it may claim acceptance.
        self.assertIn(smoke["status"], {"pending_first_green_run", "green_on_hosted_runner"})
        self.assertNotEqual(smoke["status"], "accepted")
        if "receipt" in smoke:
            self.assertTrue((ROOT / smoke["receipt"]).is_file(), smoke["receipt"])
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

    def test_unpinned_fail_closed_check_precedes_every_install_and_plan_line(self):
        # Mirrors the Linux script: the pin lookup for the whole selected set
        # runs before install_pin is ever called, so neither an install nor a
        # --plan line can happen ahead of the exit-3 refusal.
        check_index = self.text.index("unpinned_ids=()")
        core_loop_index = self.text.index("for core_id in node uv gh")
        self.assertLess(check_index, core_loop_index)
        self.assertIn("exit 3", self.text)
        self.assertIn("--allow-unpinned", self.text)

    def test_empty_array_expansions_stay_bash_32_safe(self):
        # A stock Mac's /bin/bash is 3.2, where `set -u` rejects some
        # expansions of an empty array. The script guards every element
        # expansion with ${arr[@]+"${arr[@]}"} and counts with a plain
        # integer instead of ${#arr[@]}, which this host's bash 5 cannot
        # exercise; the rule is checked structurally instead.
        self.assertNotIn("${#", self.text,
                         "use an explicit counter, not ${#array[@]}, for bash 3.2")
        for guarded in ("${component_ids[@]+", "${allow_unpinned_ids[@]+"):
            self.assertIn(guarded, self.text)

    def test_brew_prerequisite_install_precedes_the_presence_check(self):
        # Item 4 mirror: on Linux the apt block moved ahead of the
        # curl/git/tar/jq presence check; here the brew formula loop does.
        brew_declare_index = self.text.index(
            "brew_formulae=(jq python@3.13 ripgrep coreutils restic shellcheck)")
        check_index = self.text.index(
            "for required in curl git tar shasum unzip jq mktemp")
        self.assertLess(
            brew_declare_index, check_index,
            "the brew formula loop must run before the prerequisite presence check")
        self.assertIn("Missing prerequisites: %s", self.text)
        self.assertIn("exit 4", self.text)

    def test_brew_formula_loop_installs_only_what_is_missing_bash_32_safe(self):
        # brew list --versions is the presence oracle (not command -v: several
        # formulae install commands under a different name), guarded exactly
        # like every other empty-array expansion in this script, and gated on
        # skip_system==0 && plan_mode==0 so --plan and --skip-system-packages
        # never invoke brew.
        self.assertIn('brew list --versions "$formula"', self.text)
        self.assertIn('brew install "${missing_formulae[@]}"', self.text)
        self.assertIn('if [[ "$skip_system" == 0 && "$plan_mode" == 0 ]]; then', self.text)

    def test_plan_mode_lists_the_brew_formulae_it_would_install(self):
        self.assertIn(
            'printf \'plan brew formulae (installed only if brew list --versions reports them missing): %s\\n\' "${brew_formulae[*]}"',
            self.text,
        )

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
        self.assertIn("--allow-unpinned", result.stdout)
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

    # Every network or package-manager command the script could reach. A
    # --plan run must invoke none of them; each shim only logs that it ran.
    RECORDED_COMMANDS = ("curl", "wget", "brew", "npm", "npx", "node", "corepack",
                         "git", "gh", "uv", "uvx", "pip", "pip3", "softwareupdate",
                         "xcode-select", "installer", "nc", "ssh", "scp", "rsync")

    def _recorder(self, directory: Path, log: Path) -> Path:
        recorder = directory / "recorder"
        recorder.mkdir()
        for name in self.RECORDED_COMMANDS:
            shim = recorder / name
            shim.write_text(f'#!/bin/sh\nprintf "%s %s\\n" "{name}" "$*" >> "{log}"\nexit 0\n')
            shim.chmod(0o755)
        return recorder

    def _plan_with_recorder(self, tmp_path: Path, args, script=None):
        log = tmp_path / "invocations.log"
        recorder = self._recorder(tmp_path, log)
        shim = macos_shim(tmp_path)
        eco_root = tmp_path / "eco"
        result = self.run_script(
            ["--plan", "--profile", PROFILE_ID, *args],
            env={"PATH": f"{shim}{os.pathsep}{recorder}{os.pathsep}{os.environ['PATH']}",
                 "ECO_INSTALL_ROOT": str(eco_root)},
            script=script,
        )
        invocations = log.read_text() if log.exists() else ""
        return result, invocations, eco_root

    def test_plan_invokes_no_network_or_package_manager_command(self):
        for args in (["--skip-system-packages"], []):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as tmp:
                result, invocations, eco_root = self._plan_with_recorder(Path(tmp), args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("nothing was downloaded or installed", result.stdout)
                self.assertEqual(invocations, "",
                                 f"--plan invoked network/package commands:\n{invocations}")
                self.assertFalse(list(eco_root.glob("tools/*/*")))
                self.assertFalse(list(eco_root.glob("downloads/*")))

    def test_plan_recorder_catches_an_injected_network_call(self):
        # Control: the same harness on a copy with one curl call added to the
        # plan path must record it, so the test above cannot pass vacuously.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adoption_dir = tmp_path / "adoption"
            adoption_dir.mkdir()
            for name in ("manifest.json", "pins-macos-arm64.json"):
                (adoption_dir / name).write_text((ROOT / "adoption" / name).read_text())
            text = SCRIPT_PATH.read_text()
            marker = "for core_id in node uv gh; do"
            self.assertEqual(text.count(marker), 1)
            script_copy = adoption_dir / "bootstrap-macos.sh"
            script_copy.write_text(text.replace(
                marker, "curl --silent https://example.invalid/probe\n" + marker))
            result, invocations, _ = self._plan_with_recorder(
                tmp_path, ["--skip-system-packages"], script=script_copy)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("curl --silent https://example.invalid/probe", invocations)

    def test_install_root_that_resolves_to_home_or_root_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()
            link = tmp_path / "home-link"
            link.symlink_to(home)
            shim = macos_shim(tmp_path)
            roots = {"home-dot": f"{home}/.", "home-symlink": str(link),
                     "home-parent-walk": f"{home}/../home"}
            if not os.access("/", os.W_OK):
                roots["filesystem-root"] = "/."
            for label, root in roots.items():
                with self.subTest(root=label):
                    result = self.run_script(
                        ["--plan", "--profile", PROFILE_ID, "--skip-system-packages"],
                        env={"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                             "HOME": str(home), "ECO_INSTALL_ROOT": root},
                    )
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("ECO_INSTALL_ROOT must name a dedicated", result.stderr)
                    self.assertEqual(sorted(p.name for p in home.iterdir()), [],
                                     "installation children were created in HOME")

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


def _shell_functions(text: str, *names: str) -> str:
    """The source of top-level shell functions, from `name() {` to its `}`."""
    blocks = []
    for name in names:
        match = re.search(rf"(?ms)^{re.escape(name)}\(\) \{{\n.*?^\}}\n", text)
        assert match, f"function {name} not found"
        blocks.append(match.group(0))
    return "".join(blocks)


class LlamaWrapperQuotingTests(unittest.TestCase):
    """Local integration check of the generated llama-server wrapper.

    install_llama_cpp and find_one are extracted verbatim from the script and
    run with fetch stubbed out and a pre-built archive, so no network is used.
    The install root deliberately contains shell syntax.
    """

    def test_install_path_with_shell_syntax_is_data_in_the_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / 'eco $(touch PWNED) `touch PWNED2` "q" \'s\' $HOME'
            for child in ("bin", "downloads", "tools"):
                (root / child).mkdir(parents=True)
            stage = tmp_path / "stage"
            stage.mkdir()
            source = tmp_path / "src" / "llama"
            source.mkdir(parents=True)
            server = source / "llama-server"
            server.write_text('#!/bin/sh\nprintf "%s\\n%s\\n" "$0" "$DYLD_LIBRARY_PATH"\n')
            server.chmod(0o755)
            archive = root / "downloads" / "llama.tar.gz"
            subprocess.run(["tar", "-czf", str(archive), "-C", str(source.parent), "llama"],
                           check=True)
            harness = tmp_path / "harness.sh"
            harness.write_text(
                "set -Eeuo pipefail\n"
                + _shell_functions(SCRIPT_PATH.read_text(), "find_one", "install_llama_cpp")
                + "fetch() { :; }\n"
                + 'ecosystem_root=$1; bin_dir="$1/bin"; cache_dir="$1/downloads"; stage_dir=$2\n'
                + "install_llama_cpp b1 https://example.invalid/llama.tar.gz unused\n")
            built = subprocess.run(["bash", str(harness), str(root), str(stage)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run(["sh", str(root / "bin" / "llama-server")],
                                 capture_output=True, text=True, timeout=60, cwd=tmp_path,
                                 env={**os.environ, "DYLD_LIBRARY_PATH": ""})
            self.assertFalse((tmp_path / "PWNED").exists(), "$(...) in the path was executed")
            self.assertFalse((tmp_path / "PWNED2").exists(), "`...` in the path was executed")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            prefix = f"{root}/tools/llama-cpp-b1"
            self.assertEqual(run.stdout.splitlines(), [f"{prefix}/llama-server", prefix])


class PlatformDependencyVerificationTests(unittest.TestCase):
    """verify_platform_dependency and install_npm's --ignore-scripts wiring,
    extracted verbatim from the script and run with a fixture pins file and a
    fake `.package-lock.json` / fake `npm`, so no network or real npm install
    is used. No macOS host ran any of this.

    Fake integrity/hash values below are assembled from concatenated string
    parts rather than written as single literals, so a fixture value shaped
    like a real secret/hash never appears as one contiguous token in this
    source file.
    """

    def _pins_fixture(self, tmp_path: Path, tool: dict) -> Path:
        pins_path = tmp_path / "pins-fixture.json"
        pins_path.write_text(json.dumps({
            "schema_version": 1, "reviewed_at": "2026-09-23", "platform": "macos-arm64",
            "source": "test fixture", "tools": [tool],
        }))
        return pins_path

    def _run_verify(self, tmp_path: Path, pins_path: Path, dep_id: str, prefix: Path):
        harness = tmp_path / "verify-harness.sh"
        harness.write_text(
            "set -Eeuo pipefail\n"
            + _shell_functions(SCRIPT_PATH.read_text(), "verify_platform_dependency")
            + f'pins_path={json.dumps(str(pins_path))}\n'
            + f'verify_platform_dependency {dep_id} {json.dumps(str(prefix))}\n'
        )
        return subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=30)

    def test_passes_when_lock_entry_matches_the_pin(self):
        # Assembled, not a single literal, per the fixture-value convention above.
        fake_integrity = "sha512-" + "".join(["QUJD", "MTIz", "eHl6"]) + "=="
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prefix = tmp_path / "tools" / "widget-1.0.0"
            lock_dir = prefix / "lib" / "node_modules"
            lock_dir.mkdir(parents=True)
            (lock_dir / ".package-lock.json").write_text(json.dumps({
                "packages": {"node_modules/@scope/widget-darwin-arm64": {
                    "version": "1.0.0-darwin-arm64", "integrity": fake_integrity,
                }},
            }))
            pins_path = self._pins_fixture(tmp_path, {
                "id": "widget", "version": "1.0.0", "kind": "npm", "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": {
                    "name": "@scope/widget-darwin-arm64", "resolved_package": "@scope/widget",
                    "version": "1.0.0-darwin-arm64", "integrity": fake_integrity,
                },
            })
            result = self._run_verify(tmp_path, pins_path, "widget", prefix)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Verified platform dependency", result.stdout)

    def test_fails_closed_on_integrity_mismatch(self):
        pinned_integrity = "sha512-" + "".join(["QUJD", "MTIz", "eHl6"]) + "=="
        installed_integrity = "sha512-" + "".join(["ZGlm", "ZmVy", "ZW50"]) + "=="
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prefix = tmp_path / "tools" / "widget-1.0.0"
            lock_dir = prefix / "lib" / "node_modules"
            lock_dir.mkdir(parents=True)
            (lock_dir / ".package-lock.json").write_text(json.dumps({
                "packages": {"node_modules/@scope/widget-darwin-arm64": {
                    "version": "1.0.0-darwin-arm64", "integrity": installed_integrity,
                }},
            }))
            pins_path = self._pins_fixture(tmp_path, {
                "id": "widget", "version": "1.0.0", "kind": "npm", "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": {
                    "name": "@scope/widget-darwin-arm64", "resolved_package": "@scope/widget",
                    "version": "1.0.0-darwin-arm64", "integrity": pinned_integrity,
                },
            })
            result = self._run_verify(tmp_path, pins_path, "widget", prefix)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Refusing widget", result.stderr)
            self.assertIn("platform dependency @scope/widget-darwin-arm64", result.stderr)

    def test_falls_back_to_package_json_integrity_when_no_lockfile(self):
        fake_integrity = "sha512-" + "".join(["cGtn", "aW50", "ZWdy"]) + "=="
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prefix = tmp_path / "tools" / "widget-1.0.0"
            pkg_dir = prefix / "lib" / "node_modules" / "@scope" / "widget-darwin-arm64"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "package.json").write_text(json.dumps({
                "name": "@scope/widget", "version": "1.0.0-darwin-arm64", "_integrity": fake_integrity,
            }))
            pins_path = self._pins_fixture(tmp_path, {
                "id": "widget", "version": "1.0.0", "kind": "npm", "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": {
                    "name": "@scope/widget-darwin-arm64", "resolved_package": "@scope/widget",
                    "version": "1.0.0-darwin-arm64", "integrity": fake_integrity,
                },
            })
            result = self._run_verify(tmp_path, pins_path, "widget", prefix)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fails_closed_when_neither_lockfile_nor_package_json_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prefix = tmp_path / "tools" / "widget-1.0.0"
            (prefix / "lib" / "node_modules").mkdir(parents=True)
            pins_path = self._pins_fixture(tmp_path, {
                "id": "widget", "version": "1.0.0", "kind": "npm", "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": {
                    "name": "@scope/widget-darwin-arm64", "resolved_package": "@scope/widget",
                    "version": "1.0.0-darwin-arm64", "integrity": "sha512-" + "x" * 20 + "==",
                },
            })
            result = self._run_verify(tmp_path, pins_path, "widget", prefix)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("fail closed", result.stderr)

    def test_is_a_no_op_when_the_pin_has_no_platform_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prefix = tmp_path / "tools" / "plain-1.0.0"
            prefix.mkdir(parents=True)
            pins_path = self._pins_fixture(tmp_path, {
                "id": "plain", "version": "1.0.0", "kind": "npm", "url": "https://registry.npmjs.org/plain/-/plain-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
            })
            result = self._run_verify(tmp_path, pins_path, "plain", prefix)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), "")

    def test_install_npm_passes_ignore_scripts_only_when_the_pin_sets_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for ignore_scripts, expect_flag in (("true", True), ("false", False)):
                with self.subTest(ignore_scripts=ignore_scripts):
                    case_dir = tmp_path / ignore_scripts
                    eco_root = case_dir / "eco"
                    (eco_root / "downloads").mkdir(parents=True)
                    (eco_root / "tools").mkdir(parents=True)
                    npm_log = case_dir / "npm-invocations.log"
                    npm_shim_dir = case_dir / "npm-shim"
                    npm_shim_dir.mkdir(parents=True)
                    fake_npm = npm_shim_dir / "npm"
                    fake_npm.write_text(
                        "#!/bin/sh\n"
                        f'printf "%s\\n" "$*" >> {json.dumps(str(npm_log))}\n'
                        'for arg in "$@"; do\n'
                        '  case "$arg" in\n'
                        '    --prefix) expect_prefix=1 ;;\n'
                        '    *) if [ "${expect_prefix:-0}" = 1 ]; then mkdir -p "$arg/bin"; expect_prefix=0; fi ;;\n'
                        '  esac\n'
                        'done\n'
                    )
                    fake_npm.chmod(0o755)
                    archive = eco_root / "downloads" / "placeholder.tgz"
                    archive.write_text("placeholder")
                    pins_path = self._pins_fixture(case_dir, {
                        "id": "widget", "version": "1.0.0", "kind": "npm",
                        "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                        "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                        "checksum_ref": "test", "install_note": "test",
                    })
                    harness = case_dir / "install-npm-harness.sh"
                    harness.write_text(
                        "set -Eeuo pipefail\n"
                        + _shell_functions(SCRIPT_PATH.read_text(), "npm_package_name",
                                           "verify_platform_dependency", "install_npm")
                        + "fetch() { :; }\n"
                        + f'pins_path={json.dumps(str(pins_path))}\n'
                        + f'ecosystem_root={json.dumps(str(eco_root))}\n'
                        + f'bin_dir={json.dumps(str(eco_root / "bin"))}\n'
                        + f'cache_dir={json.dumps(str(eco_root / "downloads"))}\n'
                        + f'install_npm widget 1.0.0 https://registry.npmjs.org/widget/-/widget-1.0.0.tgz unused {ignore_scripts}\n'
                    )
                    result = subprocess.run(
                        ["bash", str(harness)], capture_output=True, text=True, timeout=30,
                        env={**os.environ, "PATH": f"{npm_shim_dir}{os.pathsep}{os.environ['PATH']}"},
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    logged = npm_log.read_text() if npm_log.exists() else ""
                    self.assertEqual("--ignore-scripts" in logged, expect_flag, logged)


class UnpinnedComponentFailClosedTests(unittest.TestCase):
    """A selected component with no pin at all fails closed (exit 3) before
    anything is installed, and in --plan mode too, unless it is named in
    --allow-unpinned. Mirrors the Linux UnpinnedComponentFailClosedTests in
    tests/test_adoption_bootstrap.py. The fixture is a copy of the shipped
    pins file with a pin entry removed, so every run below stays offline.
    No macOS host ran any of this: Linux plus the uname/sw_vers shim only.
    """

    def _fixture(self, tmp_path: Path, drop_pins=("qdrant",)):
        adoption_dir = tmp_path / "adoption"
        adoption_dir.mkdir()
        script_copy = adoption_dir / "bootstrap-macos.sh"
        script_copy.write_text(SCRIPT_PATH.read_text())
        script_copy.chmod(0o755)
        (adoption_dir / "manifest.json").write_text(MANIFEST_PATH.read_text())
        pins = load(PINS_PATH)
        kept = [tool for tool in pins["tools"] if tool["id"] not in drop_pins]
        self.assertEqual(len(kept), len(pins["tools"]) - len(drop_pins),
                         "the fixture must really remove a shipped pin entry")
        pins["tools"] = kept
        (adoption_dir / "pins-macos-arm64.json").write_text(json.dumps(pins))
        return script_copy

    def _run(self, script, shim, eco_root, extra_args=()):
        return subprocess.run(
            ["bash", str(script), "--plan", "--profile", PROFILE_ID,
             "--skip-system-packages", *extra_args],
            capture_output=True, text=True, timeout=60,
            env={**os.environ,
                 "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                 "ECO_INSTALL_ROOT": str(eco_root)},
        )

    def test_unpinned_selected_component_exits_3_in_plan_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            script = self._fixture(tmp_path)
            eco_root = tmp_path / "eco"
            result = self._run(script, macos_shim(tmp_path), eco_root)
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("No pin in", result.stderr)
            self.assertIn("qdrant", result.stderr)
            self.assertIn("--allow-unpinned", result.stderr)
            # The refusal comes before install_pin runs at all, so --plan has
            # not printed a single component line either.
            self.assertNotIn("plan node", result.stdout)
            self.assertFalse(
                eco_root.exists() and any(eco_root.glob("tools/*/*")),
                "no tool files should have been installed before the refusal")

    def test_allow_unpinned_skips_it_and_the_plan_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            script = self._fixture(tmp_path)
            eco_root = tmp_path / "eco"
            result = self._run(script, macos_shim(tmp_path), eco_root,
                               extra_args=["--allow-unpinned", "qdrant"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Allowed unpinned components", result.stdout)
            self.assertIn("qdrant", result.stdout.split("\n")[0])
            self.assertIn("No pin for component qdrant", result.stderr)
            self.assertRegex(result.stdout, r"(?m)^plan node\s")
            self.assertFalse(
                eco_root.exists() and any(eco_root.glob("tools/*/*")),
                "--plan must still install nothing")

    def test_allow_unpinned_equals_form_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            script = self._fixture(tmp_path)
            eco_root = tmp_path / "eco"
            result = self._run(script, macos_shim(tmp_path), eco_root,
                               extra_args=["--allow-unpinned=qdrant"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Allowed unpinned components", result.stdout)

    def test_partial_allow_unpinned_still_fails_closed_on_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            script = self._fixture(tmp_path, drop_pins=("qdrant", "mcporter"))
            eco_root = tmp_path / "eco"
            result = self._run(script, macos_shim(tmp_path), eco_root,
                               extra_args=["--allow-unpinned", "qdrant"])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            refusal = result.stderr.split("No pin in", 1)[-1].split("\n")[0]
            self.assertIn("mcporter", refusal)
            self.assertNotIn("qdrant", refusal)

    def test_allow_unpinned_without_a_value_exits_two(self):
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), "--profile", PROFILE_ID,
             "--allow-unpinned"],
            capture_output=True, text=True, timeout=60, env={**os.environ},
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("--allow-unpinned requires", result.stderr)

    def test_socraticode_is_pinned_so_the_shipped_profile_needs_no_documented_skip(self):
        # socraticode used to be a documented, unpinned skip; it now has a
        # reviewed npm pin (adoption/pins-macos-arm64.json), so the empty
        # documented_unpinned_ids stays a mechanism with nothing to exempt,
        # and the shipped --plan reaches exit 0 with no "Allowed unpinned"
        # line at all -- not because socraticode is silently skipped, but
        # because every selected component actually has a pin.
        self.assertIn("documented_unpinned_ids=()", SCRIPT_PATH.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            result = subprocess.run(
                ["bash", str(SCRIPT_PATH), "--plan", "--profile", PROFILE_ID,
                 "--skip-system-packages"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ,
                     "PATH": f"{macos_shim(tmp_path)}{os.pathsep}{os.environ['PATH']}",
                     "ECO_INSTALL_ROOT": str(eco_root)},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Allowed unpinned components", result.stdout)
            self.assertRegex(result.stdout, r"(?m)^plan socraticode\s")


class PrerequisitesBeforeAndAfterBrewTests(unittest.TestCase):
    """--skip-system-packages with a missing prerequisite lists it and exits 4
    (not 1), the Linux script's item-4 behaviour. PATH is restricted to a shim
    directory that omits jq, so the check itself reports it without brew,
    network or a real macOS host."""

    def test_skip_system_packages_with_a_hidden_prerequisite_exits_4(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shim = prerequisite_shim(tmp_path, omit=("jq",))
            eco_root = tmp_path / "eco"
            result = subprocess.run(
                [shutil.which("bash"), str(SCRIPT_PATH), "--profile", PROFILE_ID,
                 "--skip-system-packages"],
                capture_output=True, text=True, timeout=60,
                env={"PATH": str(shim), "HOME": os.environ.get("HOME", str(tmp_path)),
                     "ECO_INSTALL_ROOT": str(eco_root)},
            )
            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            self.assertIn("Missing prerequisites", result.stderr)
            self.assertIn("jq", result.stderr)
            self.assertIn("--skip-system-packages", result.stderr)
            self.assertFalse(eco_root.exists(),
                             "the prerequisite check must run before any install root is made")

    def test_every_prerequisite_present_gets_past_the_check(self):
        # Control for the test above: the same shim with jq linked reaches the
        # plan instead of exiting 4.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shim = prerequisite_shim(tmp_path)
            eco_root = tmp_path / "eco"
            result = subprocess.run(
                [shutil.which("bash"), str(SCRIPT_PATH), "--plan", "--profile",
                 PROFILE_ID, "--skip-system-packages"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ,
                     "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                     "ECO_INSTALL_ROOT": str(eco_root)},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Missing prerequisites", result.stderr)


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

    def test_page_documents_the_bootstrap_usage_and_exit_codes(self):
        self.assertIn("--allow-unpinned <id,id,...>", self.page)
        self.assertIn("--skip-system-packages", self.page)
        for row in ("| 0 |", "| 1 |", "| 2 |", "| 3 |", "| 4 |"):
            self.assertIn(row, self.page, f"exit code row {row} missing")
        self.assertIn("bootstrap-linux.sh", self.page)

    def test_page_records_the_python_313_requirement(self):
        self.assertIn("brew install python@3.13", self.page)
        self.assertIn("3.9", self.page)


if __name__ == "__main__":
    unittest.main()
