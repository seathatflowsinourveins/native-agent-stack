"""Static and shimmed checks for the drafted macOS arm64 adoption bootstrap.

No macOS host ran anything here. The script is exercised on Linux through a
temporary PATH shim that makes `uname`/`sw_vers` answer as Apple Silicon macOS,
and only in `--plan` mode: no network access, no download, no installation.
Every assertion below is local_integration or structural evidence; the pinned
checksums themselves are independent observations of publisher checksum files,
release asset digests and re-hashed downloads recorded in the pins file.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
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
VALID_KINDS = {"tarball", "zip", "npm", "native"}
VALID_CHECKSUM_SOURCES = {
    "publisher_checksum_file",
    "publisher_checksum_sidecar",
    "github_release_asset_digest_plus_local_rehash",
    "npm_registry_integrity_crosscheck",
    # 2026-09-23: claude-code's native pin's checksum is cross-checked
    # against the release manifest.json plus an independent re-download and
    # re-hash of the actual served binary (see NativeClaudeCodePinTests).
    "manifest_crosscheck",
}
PROFILE_ID = "macos-arm64-foundation"
# Every macos-arm64-foundation component now has a pin (socraticode's npm pin
# closed the last gap); documented_unpinned_ids in the script is empty and
# this set stays empty as the corresponding test-side mechanism, so a future
# undocumented gap is still caught instead of silently reusing a stale list.
DOCUMENTED_SKIPS = set()
SHELLCHECK = shutil.which("shellcheck")


def _find_bash32() -> str | None:
    """A real bash 3.2 binary, if one is reachable, for dynamic evidence.

    On a real Mac /bin/bash genuinely is bash 3.2, so this finds it there
    with no extra setup. Off Mac, set BASH32_BINARY to a real bash 3.2
    build (this project's own 2026-09-23 fix round compiled one locally to
    reproduce the exact hosted-CI abort dynamically, not just structurally).
    Never bash 5: its `set -u` no longer rejects an empty array expansion at
    all, so it cannot exercise this rule either way.
    """
    candidates = [os.environ.get("BASH32_BINARY", ""), "/bin/bash", shutil.which("bash") or ""]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run([candidate, "--version"], capture_output=True, text=True, timeout=5)
        except OSError:
            continue
        if "version 3.2" in result.stdout:
            return candidate
    return None


BASH32 = _find_bash32()


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
                # A native pin (2026-09-23: claude-code) encodes the platform
                # in a URL path segment (.../darwin-arm64/claude), not the
                # bare filename, so check the whole URL there instead of
                # just its last segment.
                haystack = tool["url"] if tool.get("kind") == "native" else asset
                self.assertRegex(
                    haystack,
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

    def test_client_npm_pins_name_and_pin_their_darwin_arm64_platform_dependency(self):
        # Once documented as "unpinned" (round 1); codex still carries a real
        # platform_dependency with its own verified sha256, so this checks
        # both that install_note still names it and that it is genuinely
        # pinned, not merely mentioned. claude-code moved to a native pin
        # (2026-09-23, see NativeClaudeCodePinTests below) and no longer has
        # a platform_dependency to check here.
        by_id = {tool["id"]: tool for tool in self.pins["tools"]}
        self.assertIn("@openai/codex-darwin-arm64", by_id["codex"]["install_note"])
        dep = by_id["codex"]["platform_dependency"]
        self.assertEqual(dep["name"], "@openai/codex-darwin-arm64")
        self.assertRegex(dep["sha256"], SHA256_HEX)


class NativeClaudeCodePinTests(unittest.TestCase):
    """2026-09-23: claude-code moved from an npm wrapper + platform_dependency
    postinstall-copy pin to the native self-installing binary, matching the
    linux-x86_64 pin and ~/codex-ecosystem/bin/bootstrap-linux.sh's
    own claude-code step."""

    def setUp(self):
        self.pins = json.loads(PINS_PATH.read_text())
        self.linux_pins = json.loads(LINUX_PINS_PATH.read_text())
        self.by_id = {tool["id"]: tool for tool in self.pins["tools"]}
        self.linux_by_id = {tool["id"]: tool for tool in self.linux_pins["tools"]}

    def test_claude_code_is_a_native_pin(self):
        tool = self.by_id["claude-code"]
        self.assertEqual(tool["kind"], "native")
        self.assertEqual(tool["version"], "2.1.280")
        self.assertEqual(tool["version"], self.linux_by_id["claude-code"]["version"])
        self.assertRegex(tool["sha256"], SHA256_HEX)
        self.assertIn("darwin-arm64", tool["url"])
        self.assertIn("2.1.280", tool["url"])
        self.assertNotIn("platform_dependency", tool)

    def test_claude_code_sha256_differs_from_linux_binary(self):
        # Different platform binaries, so different bytes and different
        # checksums; this pin must not accidentally reuse the linux hash.
        self.assertNotEqual(self.by_id["claude-code"]["sha256"],
                             self.linux_by_id["claude-code"]["sha256"])

    def test_bootstrap_macos_has_a_native_pin_case(self):
        text = SCRIPT_PATH.read_text()
        self.assertIn("install_native()", text)
        self.assertIn("*-native)", text)
        self.assertIn('"$download" install "$version"', text)

    def test_mcporter_note_does_not_claim_its_tarball_is_the_whole_install(self):
        # `npm view mcporter@0.13.13 dependencies bundleDependencies` (2026-09-22):
        # ten registry-resolved runtime dependencies, none bundled; rolldown@1.2.8
        # in turn selects a native darwin-arm64 binding.
        note = {tool["id"]: tool for tool in self.pins["tools"]}["mcporter"]["install_note"]
        self.assertNotIn("whole install", note)
        self.assertIn("UNPINNED", note)
        self.assertIn("rolldown", note)
        self.assertIn("@rolldown/binding-darwin-arm64", note)


class EmbeddingModelPinTests(unittest.TestCase):
    """Round 3h (2026-09-23 readiness audit defect): the llama-embed agent
    had no model file at all. pins-macos-arm64.json's own separate
    "models" section (never "tools", so it is never swept into
    ProfileCoverageTests' manifest.json cross-check) carries the pin
    install_embed_model (adoption/bootstrap-macos.sh) downloads and
    verifies."""

    def setUp(self):
        self.pins = load(PINS_PATH)

    def test_models_section_exists_with_exactly_one_pinned_embedding_model(self):
        self.assertIn("models", self.pins)
        self.assertIsInstance(self.pins["models"], list)
        self.assertEqual(len(self.pins["models"]), 1, self.pins["models"])

    def test_embedding_model_has_required_fields_and_a_verified_sha256(self):
        model = self.pins["models"][0]
        for field in ("id", "hf_repo", "hf_revision", "file", "url", "sha256",
                      "size", "checksum_source", "checksum_ref", "install_note"):
            self.assertIn(field, model, f"missing {field}")
        self.assertIsNotNone(model["sha256"])
        self.assertRegex(model["sha256"], SHA256_HEX, "sha256 is not 64 lowercase hex chars")
        self.assertIsInstance(model["size"], int)
        self.assertGreater(model["size"], 0)
        self.assertEqual(model["checksum_source"], "huggingface_lfs_oid_plus_local_rehash")
        self.assertTrue(model["checksum_ref"].strip())
        self.assertTrue(model["install_note"].strip())

    def test_embedding_model_url_matches_its_own_hf_repo_and_revision(self):
        model = self.pins["models"][0]
        self.assertTrue(model["url"].startswith("https://huggingface.co/"))
        expected_url = (
            f"https://huggingface.co/{model['hf_repo']}/resolve/{model['hf_revision']}/{model['file']}"
        )
        self.assertEqual(model["url"], expected_url)

    def test_embedding_model_id_matches_the_documented_file_stem(self):
        model = self.pins["models"][0]
        self.assertEqual(model["id"], "embeddinggemma-300M-Q8_0")
        self.assertEqual(model["file"], "embeddinggemma-300M-Q8_0.gguf")

    def test_embedding_model_never_appears_in_the_tools_section(self):
        # A "model" is not a manifest.json profile "component"; keeping it
        # entirely separate from tools[] means it is never swept into
        # ProfileCoverageTests' profile/pin cross-check, and never needs a
        # kind ("tarball"/"zip"/"npm") that does not fit a single raw file.
        tool_ids = {tool["id"] for tool in self.pins["tools"]}
        self.assertNotIn(self.pins["models"][0]["id"], tool_ids)


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
        for absent in ("sha256sum", "flock", "dpkg-query", "apt-get", "mapfile"):
            self.assertNotIn(absent, code, f"{absent} is not available on a stock Mac")
        # `realpath` the external command (a stock, pre-macOS 13 Mac has no
        # guarantee of one) must never be shelled out to; Python's
        # `os.path.realpath` function -- always spelled with the leading
        # `os.path.` attribute access below, inside a python3 -c script -- is
        # not that command and is exactly canonical_path's own guaranteed-
        # portable fallback, so it is deliberately excluded from this check.
        self.assertNotRegex(code, r"(?<!os\.path\.)\brealpath\b",
                             "realpath is not available on a stock Mac")
        self.assertIn("os.path.realpath", self.text)
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
        # integer instead of ${#arr[@]}. This host's bash 5 cannot exercise
        # the rule dynamically (its `set -u` no longer rejects an empty
        # array expansion at all); it is checked structurally here, and
        # dynamically against a real bash 3.2 binary in
        # ScriptBehaviorUnderRealBash32Tests below when one is reachable.
        # allowed_unpinned_ids specifically regressed this way once already
        # (2026-09-23 hosted macos-15 CI: "bootstrap-macos.sh: line 192:
        # allowed_unpinned_ids[@]: unbound variable"), because its assignment
        # was guarded but a later consumption of it was not.
        self.assertNotIn("${#", self.text,
                         "use an explicit counter, not ${#array[@]}, for bash 3.2")
        for guarded in ("${component_ids[@]+", "${allow_unpinned_ids[@]+",
                        "${documented_unpinned_ids[@]+", "${allowed_unpinned_ids[@]+"):
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

    def test_version_report_checks_installed_pins_lists_bin_dir_and_brew(self):
        # Declared, bounded probes replaced `--version` on every placed
        # executable, which blocked on socraticode and context-mode (both
        # start an MCP stdio server); tests/test_adoption_version_probes.py
        # runs this report step under bash 3.2 when one is available.
        self.assertIn('for id in ${installed_pin_ids[@]+"${installed_pin_ids[@]}"}; do', self.text)
        self.assertIn('for executable in "$bin_dir"/*; do', self.text)
        self.assertNotIn('"$installed_executable" --version', self.text)
        self.assertIn("brew list --versions </dev/null", self.text)
        self.assertIn('version_report="$ecosystem_root/installed-versions.txt"', self.text)

    @unittest.skipUnless(SHELLCHECK, "native shellcheck unavailable; CI installs the pinned analyzer")
    def test_shellcheck_style_is_clean(self):
        result = subprocess.run(
            [SHELLCHECK, "-S", "style", str(SCRIPT_PATH)],
            capture_output=True, text=True, timeout=120, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(BASH32, "no real bash 3.2 binary reachable (set BASH32_BINARY, or run on a real Mac)")
class ScriptBehaviorUnderRealBash32Tests(unittest.TestCase):
    """Dynamic evidence against a genuine bash 3.2 binary, not bash 5's
    relaxed nounset handling of an empty array (which cannot reproduce this
    class of bug at all). See _find_bash32's docstring for how BASH32 is
    located. No macOS host ran the full-script test below; it substitutes a
    real bash 3.2 interpreter for bash 5 while still using the Linux
    uname/sw_vers shim, which is exactly the gap that let the 2026-09-23
    hosted macos-15 CI abort ("allowed_unpinned_ids[@]: unbound variable")
    slip past this project's own bash-5-only local testing beforehand.
    """

    def test_unguarded_empty_array_expansion_actually_aborts_and_the_guard_fixes_it(self):
        unguarded = subprocess.run(
            [BASH32, "-c", 'set -u; a=(); for x in "${a[@]}"; do :; done'],
            capture_output=True, text=True, timeout=10,
        )
        self.assertNotEqual(unguarded.returncode, 0)
        self.assertIn("unbound variable", unguarded.stderr)
        guarded = subprocess.run(
            [BASH32, "-c", 'set -u; a=(); for x in ${a[@]+"${a[@]}"}; do :; done'],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(guarded.returncode, 0, guarded.stderr)

    def test_plan_mode_runs_clean_under_real_bash_32(self):
        # Full-script smoke: the exact --plan path the offline test suite
        # otherwise only ever runs under bash 5, now run with a real bash 3.2
        # interpreter under the same uname/sw_vers shim, so a regression of
        # the exact shape that broke hosted CI is caught here first.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shim = macos_shim(tmp_path)
            eco_root = tmp_path / "eco"
            result = subprocess.run(
                [BASH32, str(SCRIPT_PATH), "--plan", "--profile", PROFILE_ID, "--skip-system-packages"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                     "ECO_INSTALL_ROOT": str(eco_root)},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("nothing was downloaded or installed", result.stdout)
            for tool in load(PINS_PATH)["tools"]:
                self.assertIn(tool["sha256"], result.stdout, f"{tool['id']} sha256 not planned")

    def test_unpinned_selected_component_still_exits_3_under_real_bash_32(self):
        # The exit-3 fail-closed path (a genuinely unpinned selected
        # component) also exercises allowed_unpinned_ids when it is empty;
        # this is the same scenario the hosted CI abort actually hit.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adoption_dir = tmp_path / "adoption"
            adoption_dir.mkdir()
            script_copy = adoption_dir / "bootstrap-macos.sh"
            script_copy.write_text(SCRIPT_PATH.read_text())
            script_copy.chmod(0o755)
            (adoption_dir / "manifest.json").write_text(MANIFEST_PATH.read_text())
            pins = load(PINS_PATH)
            pins["tools"] = [tool for tool in pins["tools"] if tool["id"] != "qdrant"]
            (adoption_dir / "pins-macos-arm64.json").write_text(json.dumps(pins))
            shim = macos_shim(tmp_path)
            eco_root = tmp_path / "eco"
            result = subprocess.run(
                [BASH32, str(script_copy), "--plan", "--profile", PROFILE_ID, "--skip-system-packages"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                     "ECO_INSTALL_ROOT": str(eco_root)},
            )
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("No pin in", result.stderr)
            self.assertIn("qdrant", result.stderr)


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


def _signal_and_wait_for_exit(signal_name: str, indent: str = "    ", target_var: str = "ADOPTION_SCRIPT_PID") -> str:
    """Round 3k: a fault-injection shim's real-command-then-signal tail.

    Signals `target_var` -- the harness's own top-level PID, exported as
    `ADOPTION_SCRIPT_PID` right after its `set -Eeuo pipefail` (see
    _run_install_npm), never `$PPID` (that half is genuinely
    load-independent: see tests/test_adoption_launchd.py's
    SignalShimMechanismProofTests.test_ppid_inside_a_command_substitution_
    subshell_is_not_the_script for a deterministic, no-load reproduction).

    Round 3k's FIRST draft of this helper also polled `kill -0 "$target"`
    in a loop, waiting for the target to have fully exited before this
    shim itself returns. That design was WRONG and is not used: this shim
    is always the target's own SYNCHRONOUS foreground child (exactly how
    real npm/mv/ln are invoked), so the target cannot possibly exit --
    its own `wait()` cannot return -- while still blocked waiting for THIS
    shim to finish. A shim that waits for the target to disappear before
    it disappears itself is circular, not a handshake; it does not fail
    loudly either, since its own 30s bound always fires (proven directly:
    every affected test took ~30-63s per run in this project's first
    commit of this helper, passing only because the shim's own timeout
    path, not a real interruption, produced a nonzero exit the assertions
    happened to accept as "not 0").

    What actually determines correctness, confirmed by direct, repeated
    (bash 5.2, this host, 10/10 both with and without an added sleep)
    testing: bash defers running a trapped signal's handler until whatever
    is CURRENTLY in the foreground finishes -- here, this shim itself --
    and then services it immediately afterward, before the script's own
    next line, regardless of how long that takes. Ordering is therefore
    already guaranteed by bash's synchronous foreground-child execution
    model alone, once the signal reaches the right PID (the fix above).
    This tail still sleeps briefly (0.5s, comfortably above the 0.2-0.3s
    this project's earlier rounds used) purely as defensive margin for the
    real `kill()` syscall's effect to be recorded before this process
    image goes away -- not to "win a race" against the trap, which this
    shim structurally cannot observe completing. Same helper (and the
    same design) as tests/test_adoption_launchd.py's own copy.
    """
    p = indent
    return (
        f'{p}target="${target_var}"\n'
        f'{p}kill -{signal_name} "$target"\n'
        f'{p}sleep 0.5\n'
    )


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


NPM = shutil.which("npm")


class EmbeddingModelInstallTests(unittest.TestCase):
    """install_embed_model (round 3h), extracted verbatim from the script
    and run with a real, unmodified fetch() -- only `curl` itself is
    shimmed (a tiny script that copies a local fixture in place of the
    real network call), so the checksum verification under test is
    fetch's own real code, not a test-only reimplementation of it."""

    def _fixture(self, tmp_path: Path, content: bytes) -> tuple[Path, str]:
        fixture = tmp_path / "fixture-model.gguf"
        fixture.write_bytes(content)
        return fixture, hashlib.sha256(content).hexdigest()

    def _curl_shim(self, tmp_path: Path, fixture: Path) -> Path:
        shim = tmp_path / "curl-shim"
        shim.mkdir()
        (shim / "curl").write_text(
            "#!/bin/sh\n"
            'out=""\n'
            'prev=""\n'
            'for arg in "$@"; do\n'
            '  if [ "$prev" = "--output" ]; then out="$arg"; fi\n'
            '  prev="$arg"\n'
            "done\n"
            f'cp {str(fixture)!r} "$out"\n'
            "exit 0\n"
        )
        (shim / "curl").chmod(0o755)
        return shim

    def _run_install_embed_model(self, tmp_path: Path, pins: dict, curl_shim: Path):
        eco_root = tmp_path / "eco"
        eco_root.mkdir(exist_ok=True)
        pins_path = tmp_path / "pins.json"
        pins_path.write_text(json.dumps(pins))
        harness = tmp_path / "install-embed-model-harness.sh"
        harness.write_text(
            "set -Eeuo pipefail\n"
            + _shell_functions(SCRIPT_PATH.read_text(), "fetch", "install_embed_model")
            + f'pins_path={json.dumps(str(pins_path))}\n'
            + f'ecosystem_root={json.dumps(str(eco_root))}\n'
            + "plan_mode=0\n"
            + "install_embed_model\n"
        )
        result = subprocess.run(
            ["bash", str(harness)], capture_output=True, text=True, timeout=30,
            env={**os.environ, "PATH": f"{curl_shim}{os.pathsep}{os.environ['PATH']}"},
        )
        return result, eco_root

    def test_bootstrap_verifies_the_digest_and_fails_closed_on_a_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture, real_sha256 = self._fixture(tmp_path, b"not the real gguf content")
            curl_shim = self._curl_shim(tmp_path, fixture)
            pins = {
                "models": [{
                    "id": "embeddinggemma-300M-Q8_0",
                    "file": "embeddinggemma-300M-Q8_0.gguf",
                    "url": "https://huggingface.co/example/resolve/main/embeddinggemma-300M-Q8_0.gguf",
                    # Deliberately wrong: real_sha256 is the fixture's ACTUAL
                    # hash; this pin claims a different one, standing in for
                    # a corrupted download, an MITM'd response or a stale pin.
                    "sha256": "0" * 64,
                    "size": len(b"not the real gguf content"),
                }]
            }
            result, eco_root = self._run_install_embed_model(tmp_path, pins, curl_shim)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Checksum mismatch", result.stderr)
            installed = eco_root / "state" / "models" / "embeddinggemma-300M-Q8_0.gguf"
            self.assertFalse(installed.exists(), "a digest mismatch must never leave the file in place")

    def test_bootstrap_installs_the_model_once_the_digest_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            content = b"a small stand-in for the real 333MB gguf, hashed for real"
            fixture, real_sha256 = self._fixture(tmp_path, content)
            curl_shim = self._curl_shim(tmp_path, fixture)
            pins = {
                "models": [{
                    "id": "embeddinggemma-300M-Q8_0",
                    "file": "embeddinggemma-300M-Q8_0.gguf",
                    "url": "https://huggingface.co/example/resolve/main/embeddinggemma-300M-Q8_0.gguf",
                    "sha256": real_sha256,
                    "size": len(content),
                }]
            }
            result, eco_root = self._run_install_embed_model(tmp_path, pins, curl_shim)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Installed embedding model", result.stdout)
            installed = eco_root / "state" / "models" / "embeddinggemma-300M-Q8_0.gguf"
            self.assertTrue(installed.is_file())
            self.assertEqual(installed.read_bytes(), content)
            self.assertEqual(hashlib.sha256(installed.read_bytes()).hexdigest(), real_sha256)

    def test_a_null_sha256_pin_refuses_before_any_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture, _ = self._fixture(tmp_path, b"irrelevant")
            curl_shim = self._curl_shim(tmp_path, fixture)
            pins = {
                "models": [{
                    "id": "embeddinggemma-300M-Q8_0",
                    "file": "embeddinggemma-300M-Q8_0.gguf",
                    "url": "https://huggingface.co/example/resolve/main/embeddinggemma-300M-Q8_0.gguf",
                    "sha256": None,
                    "size": 0,
                }]
            }
            result, eco_root = self._run_install_embed_model(tmp_path, pins, curl_shim)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("no verified sha256", result.stderr)
            self.assertFalse((eco_root / "state" / "models").exists())

    def test_plan_mode_prints_the_pin_without_downloading(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture, real_sha256 = self._fixture(tmp_path, b"content")
            curl_shim = self._curl_shim(tmp_path, fixture)
            eco_root = tmp_path / "eco"
            eco_root.mkdir()
            pins_path = tmp_path / "pins.json"
            pins_path.write_text(json.dumps({
                "models": [{
                    "id": "embeddinggemma-300M-Q8_0",
                    "file": "embeddinggemma-300M-Q8_0.gguf",
                    "url": "https://huggingface.co/example/resolve/main/embeddinggemma-300M-Q8_0.gguf",
                    "sha256": real_sha256,
                    "size": len(b"content"),
                }]
            }))
            harness = tmp_path / "harness.sh"
            harness.write_text(
                "set -Eeuo pipefail\n"
                + _shell_functions(SCRIPT_PATH.read_text(), "fetch", "install_embed_model")
                + f'pins_path={json.dumps(str(pins_path))}\n'
                + f'ecosystem_root={json.dumps(str(eco_root))}\n'
                + "plan_mode=1\n"
                + "install_embed_model\n"
            )
            result = subprocess.run(
                ["bash", str(harness)], capture_output=True, text=True, timeout=30,
                env={**os.environ, "PATH": f"{curl_shim}{os.pathsep}{os.environ['PATH']}"},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("plan", result.stdout)
            self.assertIn(real_sha256, result.stdout)
            self.assertFalse((eco_root / "state" / "models").exists(),
                              "plan mode must never touch the network or the filesystem")


class QdrantConfigProvisionTests(unittest.TestCase):
    """provision_qdrant_config (round 3j Codex P2 thread 4), extracted
    verbatim and run standalone -- no real qdrant binary involved, only
    the config file this profile's launchd plist has nowhere else to get
    one from on a clean host."""

    def _run_provision(self, tmp_path: Path, eco_root: Path, plan_mode: str = "0"):
        harness = tmp_path / "harness.sh"
        harness.write_text(
            "set -Eeuo pipefail\n"
            + _shell_functions(SCRIPT_PATH.read_text(), "provision_qdrant_config")
            + f'ecosystem_root={json.dumps(str(eco_root))}\n'
            + f"plan_mode={plan_mode}\n"
            + "provision_qdrant_config\n"
        )
        return subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=30)

    @staticmethod
    def _parse_two_level_yaml(text):
        """Parse the flat two-level mapping examples/qdrant.yaml.example uses
        (top-level keys, two-space-indented scalar children) without PyYAML,
        which the macos-15 setup-python interpreter does not have -- this
        provisioning check must still run on macOS itself."""
        def scalar(raw):
            raw = raw.strip()
            if raw in ("null", "~", ""):
                return None
            if raw in ("true", "false"):
                return raw == "true"
            if raw.lstrip("-").isdigit():
                return int(raw)
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
                return raw[1:-1]
            return raw
        data, section = {}, None
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, sep, value = line.strip().partition(":")
            if not sep:
                raise ValueError(f"unparsable line: {line!r}")
            if line.startswith("  ") and section is not None:
                data[section][key] = scalar(value)
            elif value.strip():
                data[key], section = scalar(value), None
            else:
                data[key], section = {}, key
        return data

    def test_provisions_a_default_config_matching_the_selected_linux_recipe_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            result = self._run_provision(tmp_path, eco_root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            config_path = eco_root / "config" / "qdrant.yaml"
            self.assertTrue(config_path.is_file())
            data = self._parse_two_level_yaml(config_path.read_text())
            # Mirrors examples/qdrant.yaml.example exactly: storage under
            # $ECO_ROOT/state (never inside a version-pinned tools/<id>-
            # <version> directory a later bump can replace wholesale),
            # loopback bind, and port 16333 -- the same port
            # adoption/hosts/macos-example.json's QDRANT_URL and
            # recipes/README.md's qdrant row both name.
            self.assertEqual(data["storage"]["storage_path"], str(eco_root / "state" / "qdrant" / "storage"))
            self.assertEqual(data["storage"]["snapshots_path"], str(eco_root / "state" / "qdrant" / "snapshots"))
            self.assertEqual(data["service"]["host"], "127.0.0.1")
            self.assertEqual(data["service"]["http_port"], 16333)
            self.assertIsNone(data["service"]["grpc_port"])
            self.assertFalse(data["service"]["enable_cors"])
            self.assertFalse(data["cluster"]["enabled"])
            self.assertTrue(data["telemetry_disabled"])
            self.assertTrue((eco_root / "state" / "qdrant" / "storage").is_dir())
            self.assertTrue((eco_root / "state" / "qdrant" / "snapshots").is_dir())

    def test_never_overwrites_an_existing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            config_dir = eco_root / "config"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "qdrant.yaml"
            custom_config = "service:\n  host: 127.0.0.1\n  http_port: 26333\n# a person's own edited config\n"
            config_path.write_text(custom_config)

            result = self._run_provision(tmp_path, eco_root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("left as is", result.stdout)
            self.assertEqual(config_path.read_text(), custom_config,
                              "an existing config must never be overwritten by the default")

    def test_plan_mode_reports_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            result = self._run_provision(tmp_path, eco_root, plan_mode="1")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("plan", result.stdout)
            self.assertFalse((eco_root / "config" / "qdrant.yaml").exists(),
                              "plan mode must never touch the filesystem")

    def test_plan_mode_reports_an_existing_config_would_be_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            config_dir = eco_root / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "qdrant.yaml").write_text("# already here\n")
            result = self._run_provision(tmp_path, eco_root, plan_mode="1")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("existing", result.stdout)
            self.assertEqual((config_dir / "qdrant.yaml").read_text(), "# already here\n")


class RealNpmLockfileEvidenceTests(unittest.TestCase):
    """Regression evidence for the finding that motivated
    install_platform_dependency's design (Codex/Opus review, 2026-09-23):
    a real `npm install --global --prefix <dir> <pkg-with-an-optional-dependency>`
    writes no lockfile anywhere under the prefix and no package.json
    `_integrity` field for the resolved optional dependency, which is placed
    NESTED under the parent, not at its own top-level name. This uses real
    npm packing and installing two tiny local packages -- not a hand-built
    fixture -- so the on-disk layout comes from npm itself. If a future npm
    version changes this, this test (not install_platform_dependency, which
    no longer depends on it at all) is what will notice.
    """

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_global_prefix_install_of_an_optional_dependency_writes_no_lockfile_or_integrity_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            platform_dir = tmp_path / "platform-pkg"
            platform_dir.mkdir()
            (platform_dir / "package.json").write_text(
                json.dumps({"name": "test-platform-dep", "version": "9.9.9"}))
            (platform_dir / "marker.txt").write_text("marker\n")
            subprocess.run([NPM, "pack", "--silent", "--pack-destination", str(tmp_path)],
                            cwd=platform_dir, capture_output=True, text=True, timeout=60, check=True)
            platform_tarball = tmp_path / "test-platform-dep-9.9.9.tgz"
            self.assertTrue(platform_tarball.is_file())

            parent_dir = tmp_path / "parent-pkg"
            parent_dir.mkdir()
            (parent_dir / "package.json").write_text(json.dumps({
                "name": "test-parent-pkg", "version": "1.0.0",
                "optionalDependencies": {"test-platform-dep": f"file:{platform_tarball}"},
            }))
            subprocess.run([NPM, "pack", "--silent", "--pack-destination", str(tmp_path)],
                            cwd=parent_dir, capture_output=True, text=True, timeout=60, check=True)
            parent_tarball = tmp_path / "test-parent-pkg-1.0.0.tgz"
            self.assertTrue(parent_tarball.is_file())

            prefix = tmp_path / "prefix"
            result = subprocess.run(
                [NPM, "install", "--global", "--no-audit", "--no-fund", "--prefix", str(prefix), str(parent_tarball)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            lockfiles = list(prefix.rglob("*lock*"))
            self.assertEqual(lockfiles, [], f"expected no lockfile anywhere under {prefix}, found {lockfiles}")

            installed = list(prefix.rglob("test-platform-dep/package.json"))
            self.assertEqual(len(installed), 1, installed)
            # Nested under the parent's own node_modules, not top-level at
            # lib/node_modules/test-platform-dep.
            self.assertIn("test-parent-pkg/node_modules/test-platform-dep", str(installed[0]))
            manifest = json.loads(installed[0].read_text())
            self.assertNotIn("_integrity", manifest)


class PlatformDependencyInstallTests(unittest.TestCase):
    """install_platform_dependency and install_npm's shadow-defeating
    ordering, extracted verbatim from the script and run against real
    npm-packed local fixtures (fetch() stubbed to copy them into place
    instead of reaching the network). No macOS host ran any of this, and no
    darwin-arm64 binary is involved -- only the install mechanism, which is
    platform-independent; two fixture wrappers mimic codex's (no lifecycle
    scripts, resolves at runtime) and claude-code's (postinstall copies from
    wherever require.resolve finds the platform package) actual shapes.
    """

    @classmethod
    def setUpClassWithNpm(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(cls._tmp.name)

        def pack(directory: Path, dest: Path) -> None:
            subprocess.run([NPM, "pack", "--silent", "--pack-destination", str(dest)],
                            cwd=directory, capture_output=True, text=True, timeout=60, check=True)

        # The independently reviewed, sha256-verified platform dependency.
        verified_dir = tmp_path / "verified-platform-dep"
        verified_dir.mkdir()
        (verified_dir / "package.json").write_text(json.dumps({"name": "fixture-real-name", "version": "1.2.3"}))
        (verified_dir / "native-bin").write_text("VERIFIED_CONTENT\n")
        pack(verified_dir, tmp_path)
        cls.verified_tarball = tmp_path / "fixture-real-name-1.2.3.tgz"
        cls.verified_sha256 = hashlib.sha256(cls.verified_tarball.read_bytes()).hexdigest()

        # A same-name, same-version, DIFFERENT-content tarball standing in
        # for what an npm registry fetch (never independently verified)
        # could return; a shadow-defeating fix must never let this win.
        unverified_dir = tmp_path / "unverified-platform-dep"
        unverified_dir.mkdir()
        (unverified_dir / "package.json").write_text(json.dumps({"name": "fixture-real-name", "version": "1.2.3"}))
        (unverified_dir / "native-bin").write_text("UNVERIFIED_CONTENT\n")
        registry_sim = tmp_path / "registry-sim"
        registry_sim.mkdir()
        pack(unverified_dir, registry_sim)
        cls.unverified_tarball = registry_sim / "fixture-real-name-1.2.3.tgz"

        # codex-like: no lifecycle scripts; resolves the platform dependency
        # at (simulated) runtime, matching bin/codex.js's own shape.
        codex_like_dir = tmp_path / "codex-like-pkg"
        codex_like_dir.mkdir()
        (codex_like_dir / "package.json").write_text(json.dumps({
            "name": "fixture-codex-like", "version": "1.0.0",
            "optionalDependencies": {"widget-darwin-arm64": f"file:{cls.unverified_tarball}"},
        }))
        pack(codex_like_dir, tmp_path)
        cls.codex_like_tarball = tmp_path / "fixture-codex-like-1.0.0.tgz"
        cls.codex_like_sha256 = hashlib.sha256(cls.codex_like_tarball.read_bytes()).hexdigest()

        # claude-code-like: a postinstall that resolves the platform
        # dependency and copies its native-bin into its own bin/ file,
        # matching install.cjs's own copy-on-postinstall shape exactly.
        claude_like_dir = tmp_path / "claude-like-pkg"
        (claude_like_dir / "bin").mkdir(parents=True)
        (claude_like_dir / "bin" / "claude-like.exe").write_text("STUB\n")
        (claude_like_dir / "postinstall.js").write_text(
            'const fs = require("fs");\n'
            'const path = require("path");\n'
            'const src = path.dirname(require.resolve("widget-darwin-arm64/package.json"));\n'
            'const content = fs.readFileSync(path.join(src, "native-bin"));\n'
            'fs.writeFileSync(path.join(__dirname, "bin", "claude-like.exe"), content);\n'
            'console.log("POSTINSTALL_COPIED:" + content.toString().trim());\n'
        )
        (claude_like_dir / "package.json").write_text(json.dumps({
            "name": "fixture-claude-like", "version": "1.0.0",
            "bin": {"claude-like": "bin/claude-like.exe"},
            "optionalDependencies": {"widget-darwin-arm64": f"file:{cls.unverified_tarball}"},
            "scripts": {"postinstall": "node postinstall.js"},
        }))
        pack(claude_like_dir, tmp_path)
        cls.claude_like_tarball = tmp_path / "fixture-claude-like-1.0.0.tgz"
        cls.claude_like_sha256 = hashlib.sha256(cls.claude_like_tarball.read_bytes()).hexdigest()

    @classmethod
    def setUpClass(cls):
        if NPM:
            cls.setUpClassWithNpm()

    @classmethod
    def tearDownClass(cls):
        if NPM:
            cls._tmp.cleanup()

    def _pins_fixture(self, tmp_path: Path, tool: dict) -> Path:
        pins_path = tmp_path / "pins-fixture.json"
        pins_path.write_text(json.dumps({
            "schema_version": 1, "reviewed_at": "2026-09-23", "platform": "macos-arm64",
            "source": "test fixture", "tools": [tool],
        }))
        return pins_path

    def _platform_dependency_pin(self, binary_check: dict | None = None) -> dict:
        pin = {
            "name": "widget-darwin-arm64", "resolved_package": "fixture-real-name",
            "version": "1.2.3", "url": "https://example.invalid/verified-platform-dep.tgz",
            "sha256": self.verified_sha256, "integrity": "sha512-unused-in-this-test",
        }
        if binary_check:
            pin["postinstall_binary_check"] = binary_check
        return pin

    def _run(self, tmp_path: Path, pins_path: Path, dep_id: str, prefix: Path, fetch_body: str,
             extra_env: dict | None = None):
        harness = tmp_path / "install-platform-dep-harness.sh"
        harness.write_text(
            "set -Eeuo pipefail\n"
            + _shell_functions(SCRIPT_PATH.read_text(), "canonical_path", "npm_package_name",
                                "install_platform_dependency")
            + f'pins_path={json.dumps(str(pins_path))}\n'
            + f'cache_dir={json.dumps(str(tmp_path / "downloads"))}\n'
            + f'stage_dir={json.dumps(str(tmp_path / "stage"))}\n'
            + "fetch() { " + fetch_body + " ; }\n"
            + f'install_platform_dependency {dep_id} {json.dumps(str(prefix))}\n'
        )
        (tmp_path / "downloads").mkdir(exist_ok=True)
        (tmp_path / "stage").mkdir(exist_ok=True)
        return subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=60,
                               env={**os.environ, **(extra_env or {})})

    def _run_install_npm(self, tmp_path: Path, pins_path: Path, id_: str, version: str,
                          wrapper_archive: Path, wrapper_sha256: str, npm_package: str,
                          ignore_scripts: str = "false", extra_env: dict | None = None):
        eco_root = tmp_path / "eco"
        (eco_root / "downloads").mkdir(parents=True, exist_ok=True)
        (eco_root / "tools").mkdir(parents=True, exist_ok=True)
        (eco_root / "bin").mkdir(parents=True, exist_ok=True)
        stage_dir = tmp_path / "stage"
        stage_dir.mkdir(exist_ok=True)
        # npm_package_name derives the package name from this URL's own
        # path structure (matching a real registry tarball URL's
        # convention), which must equal the fixture tarball's actual
        # package.json "name" -- not necessarily this tool's own id_.
        wrapper_url = f"https://registry.npmjs.org/{npm_package}/-/{npm_package}-{version}.tgz"
        dep_url = "https://example.invalid/verified-platform-dep.tgz"
        harness = tmp_path / "install-npm-e2e-harness.sh"
        harness.write_text(
            "set -Eeuo pipefail\n"
            # Round 3k: exported for this harness's own fault-injection
            # shims (npm/mv/ln) to signal deterministically -- see
            # _signal_and_wait_for_exit's own comment for why, never
            # $PPID.
            + 'export ADOPTION_SCRIPT_PID="$$"\n'
            + _shell_functions(SCRIPT_PATH.read_text(), "canonical_path", "prune_old_version",
                                "npm_package_name", "install_platform_dependency", "install_npm", "cleanup")
            # The script-level pending_migration_prefix/_dest globals and the
            # EXIT trap that uses them (round 3d) are NOT part of any single
            # extracted function -- without registering the same trap here,
            # a signal or a failure after install_npm sets them would never
            # actually be recovered in this harness, unlike the real script.
            + 'pending_migration_prefix=""\n'
            + 'pending_migration_dest=""\n'
            + "trap cleanup EXIT\n"
            + "trap 'exit 130' INT\n"
            + "trap 'exit 143' TERM\n"
            + "trap 'exit 129' HUP\n"
            + f'pins_path={json.dumps(str(pins_path))}\n'
            + f'ecosystem_root={json.dumps(str(eco_root))}\n'
            + f'bin_dir={json.dumps(str(eco_root / "bin"))}\n'
            + f'cache_dir={json.dumps(str(eco_root / "downloads"))}\n'
            + f'stage_dir={json.dumps(str(stage_dir))}\n'
            # fetch() must distinguish the wrapper's own archive url from the
            # platform_dependency's url, each copied from a real local path
            # standing in for the network, never actually reaching one.
            + "fetch() {\n"
            + "  case \"$1\" in\n"
            + f"    {wrapper_url}) cp {json.dumps(str(wrapper_archive))} \"$3\" ;;\n"
            + f"    {dep_url}) cp {json.dumps(str(self.verified_tarball))} \"$3\" ;;\n"
            + "    *) echo \"fetch: unexpected url $1\" >&2; exit 1 ;;\n"
            + "  esac\n"
            + "}\n"
            + f'install_npm {id_} {version} {wrapper_url} {wrapper_sha256} {ignore_scripts}\n'
        )
        # Round 3k: 90s, not 60s -- a fault-injection shim's own bounded
        # wait for the script to react to a signal (_signal_and_wait_for_
        # exit) can itself take up to 30s under real CPU load before it
        # gives up; this must stay comfortably above npm install's own
        # time plus that 30s so a genuine slow-but-eventual pass is never
        # mistaken for a hang.
        result = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=90,
                                 env={**os.environ, **(extra_env or {})})
        return result, eco_root

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_places_the_verified_tarball_under_its_alias_name_when_no_wrapper_shadows_it(self):
        # install_platform_dependency called in isolation (no wrapper ever
        # installed at prefix/lib/node_modules/widget): require.resolve finds
        # nothing to shadow it, so it falls back to a top-level alias --
        # still Node-resolvable, still exercised end to end.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prefix = tmp_path / "tools" / "widget-1.0.0"
            pins_path = self._pins_fixture(tmp_path, {
                "id": "widget", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": self._platform_dependency_pin(),
            })
            result = self._run(tmp_path, pins_path, "widget", prefix,
                                f'cp {json.dumps(str(self.verified_tarball))} "$3"')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Installed and verified platform dependency widget-darwin-arm64", result.stdout)
            installed_pkg = prefix / "lib" / "node_modules" / "widget-darwin-arm64" / "package.json"
            self.assertTrue(installed_pkg.is_file(), list(prefix.rglob("*")))
            manifest = json.loads(installed_pkg.read_text())
            self.assertEqual(manifest["name"], "fixture-real-name")
            self.assertEqual(manifest["version"], "1.2.3")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_codex_like_wrapper_resolves_the_verified_dependency_not_the_shadowed_one(self):
        # High finding: installing the wrapper WITHOUT --omit=optional (etc.)
        # auto-fetches the unverified tarball, unverified, and nests it under
        # the wrapper's own node_modules -- which Node's require.resolve
        # checks before a top-level sibling. This proves install_npm's full
        # sequence (install --ignore-scripts, fix up, npm rebuild) makes the
        # ACTUAL resolved content the verified one, not the shadowed one.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pins_path = self._pins_fixture(tmp_path, {
                "id": "codexlike", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/fixture-codex-like/-/fixture-codex-like-1.0.0.tgz",
                "sha256": self.codex_like_sha256, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": self._platform_dependency_pin(),
            })
            result, eco_root = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            wrapper_dir = eco_root / "tools" / "codexlike-1.0.0" / "lib" / "node_modules" / "fixture-codex-like"
            content = subprocess.run(
                ["node", "-e",
                 'const p = require.resolve("widget-darwin-arm64/package.json", {paths: [process.argv[1]]});'
                 'const fs = require("fs"), path = require("path");'
                 'process.stdout.write(fs.readFileSync(path.join(path.dirname(p), "native-bin"), "utf8").trim());',
                 str(wrapper_dir)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(content.returncode, 0, content.stdout + content.stderr)
            self.assertEqual(content.stdout.strip(), "VERIFIED_CONTENT")

    def _tmp_via_symlink(self, tmp: str) -> Path:
        """A directory reached only through a symlinked ancestor, mirroring
        a real Mac's own /var -> /private/var (also /tmp -> /private/tmp):
        the exact class of path that broke install_platform_dependency's
        containment and resolution checks, since Node's require.resolve
        realpath-resolves symlinks by default. Reproduced here off-Mac so
        the fix (canonical_path, applied to both sides of every comparison)
        has real, non-simulated evidence on this Linux host too."""
        tmp_path = Path(tmp)
        real_var = tmp_path / "private" / "var"
        real_var.mkdir(parents=True)
        symlinked_var = tmp_path / "var"
        symlinked_var.symlink_to(real_var, target_is_directory=True)
        return symlinked_var

    def test_places_the_verified_tarball_correctly_when_the_prefix_is_reached_through_a_symlink(self):
        # Round 3b, Opus Medium M1 / hosted macos-15 run 35820422561: seven
        # PlatformDependencyInstallTests failed on a real Mac with "does not
        # resolve to .../tools/widget-1.0.0/.../package.json ... resolved to
        # /priva[te/var/...]" -- expected_nested was built from the ORIGINAL
        # (non-canonical) prefix, but require.resolve returns the
        # realpath-resolved (/private/var) form. Reproduced here with an
        # equivalent symlinked tmp root standing in for /var.
        with tempfile.TemporaryDirectory() as tmp:
            symlinked_root = self._tmp_via_symlink(tmp)
            tmp_path = Path(tmp)
            prefix = symlinked_root / "tools" / "widget-1.0.0"
            pins_path = self._pins_fixture(tmp_path, {
                "id": "widget", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": self._platform_dependency_pin(),
            })
            result = self._run(tmp_path, pins_path, "widget", prefix,
                                f'cp {json.dumps(str(self.verified_tarball))} "$3"')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Installed and verified platform dependency widget-darwin-arm64", result.stdout)
            installed_pkg = prefix / "lib" / "node_modules" / "widget-darwin-arm64" / "package.json"
            self.assertTrue(installed_pkg.is_file(), list(prefix.rglob("*")))
            manifest = json.loads(installed_pkg.read_text())
            self.assertEqual(manifest["name"], "fixture-real-name")
            self.assertEqual(manifest["version"], "1.2.3")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_codex_like_wrapper_resolves_the_verified_dependency_when_the_ecosystem_root_is_reached_through_a_symlink(self):
        # Same finding as the previous test, exercised through the full
        # install_npm path (the atomic staged-swap plus
        # install_platform_dependency) with ecosystem_root itself reached
        # through a symlink -- matching either a real Mac's ECO_INSTALL_ROOT
        # default (under $HOME, not itself under /var, but staged installs
        # go through stage_dir under ecosystem_root either way) or a
        # symlinked TMPDIR-based fixture root, the two cases the coordinator
        # named for this reproduction.
        with tempfile.TemporaryDirectory() as tmp:
            symlinked_root = self._tmp_via_symlink(tmp)
            tmp_path = Path(tmp)
            pins_path = self._pins_fixture(tmp_path, {
                "id": "codexlike", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/fixture-codex-like/-/fixture-codex-like-1.0.0.tgz",
                "sha256": self.codex_like_sha256, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": self._platform_dependency_pin(),
            })
            result, eco_root = self._run_install_npm(
                symlinked_root, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            wrapper_dir = eco_root / "tools" / "codexlike-1.0.0" / "lib" / "node_modules" / "fixture-codex-like"
            content = subprocess.run(
                ["node", "-e",
                 'const p = require.resolve("widget-darwin-arm64/package.json", {paths: [process.argv[1]]});'
                 'const fs = require("fs"), path = require("path");'
                 'process.stdout.write(fs.readFileSync(path.join(path.dirname(p), "native-bin"), "utf8").trim());',
                 str(wrapper_dir)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(content.returncode, 0, content.stdout + content.stderr)
            self.assertEqual(content.stdout.strip(), "VERIFIED_CONTENT")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_a_decoy_node_modules_outside_the_prefix_is_never_deleted_or_trusted(self):
        # Medium finding: Node's require.resolve, even given an explicit
        # `paths` array, still searches its GLOBAL_FOLDERS fallback (NODE_PATH
        # entries, $HOME/.node_modules, etc. -- Node's own module docs).
        # Measured directly: with no wrapper installed yet (nothing nested to
        # find in `paths`), setting NODE_PATH to a decoy directory makes
        # require.resolve return a path OUTSIDE the prefix entirely. Before
        # this fix, install_platform_dependency would have treated that as
        # the nested copy and `rm -rf`'d whatever NODE_PATH happened to name
        # -- a real, exploitable arbitrary-path deletion, not merely a
        # theoretical one. This proves the decoy survives completely
        # untouched and the verified content still lands correctly, in the
        # top-level alias fallback this same function already uses for a
        # genuine platform mismatch.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            decoy_dir = tmp_path / "decoy-node-path"
            decoy_pkg = decoy_dir / "widget-darwin-arm64"
            decoy_pkg.mkdir(parents=True)
            (decoy_pkg / "package.json").write_text(
                json.dumps({"name": "decoy-package", "version": "0.0.1-DECOY"}))
            (decoy_pkg / "marker.txt").write_text("DECOY_CONTENT\n")
            decoy_mtime_before = (decoy_pkg / "marker.txt").stat().st_mtime

            prefix = tmp_path / "tools" / "widget-1.0.0"
            # No wrapper is ever installed at prefix/lib/node_modules/widget:
            # require.resolve's explicit `paths` search finds nothing there,
            # so (without this fix) it would fall through to NODE_PATH and
            # resolve the decoy instead.
            pins_path = self._pins_fixture(tmp_path, {
                "id": "widget", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": self._platform_dependency_pin(),
            })
            result = self._run(tmp_path, pins_path, "widget", prefix,
                                f'cp {json.dumps(str(self.verified_tarball))} "$3"',
                                extra_env={"NODE_PATH": str(decoy_dir)})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            # The decoy is completely untouched: still present, same content,
            # same mtime (never rm -rf'd and never overwritten in place).
            self.assertTrue(decoy_pkg.is_dir())
            self.assertEqual((decoy_pkg / "marker.txt").read_text(), "DECOY_CONTENT\n")
            self.assertEqual((decoy_pkg / "marker.txt").stat().st_mtime, decoy_mtime_before)

            # The verified content still lands correctly, at the top-level
            # alias fallback -- the decoy is never trusted as the nested copy.
            fallback_pkg = prefix / "lib" / "node_modules" / "widget-darwin-arm64"
            self.assertTrue(fallback_pkg.is_dir())
            manifest = json.loads((fallback_pkg / "package.json").read_text())
            self.assertEqual(manifest["name"], "fixture-real-name")
            self.assertEqual(manifest["version"], "1.2.3")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_claude_code_like_wrapper_postinstall_copies_the_verified_dependency(self):
        # Same High finding, for the postinstall-copies-at-install-time shape
        # (install.cjs): the copy must happen AFTER the fix-up, or it copies
        # the unverified bytes into bin/ once and the later fix-up is moot.
        # postinstall_binary_check exercises install_npm's own cmp assertion
        # (Low finding: confirm what actually landed in bin/, not just that
        # npm rebuild exited 0), matching the real pin's field for claude-code.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pins_path = self._pins_fixture(tmp_path, {
                "id": "claudelike", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/fixture-claude-like/-/fixture-claude-like-1.0.0.tgz",
                "sha256": self.claude_like_sha256, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": self._platform_dependency_pin(
                    binary_check={"platform_file": "native-bin", "wrapper_file": "bin/claude-like.exe"}),
            })
            result, eco_root = self._run_install_npm(
                tmp_path, pins_path, "claudelike", "1.0.0", self.claude_like_tarball, self.claude_like_sha256,
                npm_package="fixture-claude-like")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("byte-identical", result.stdout)
            # npm rebuild's own stdout (including the postinstall's
            # console.log) is redirected to /dev/null, matching every other
            # npm invocation in install_npm; the file it actually wrote is
            # the real evidence.
            wrapper_dir = eco_root / "tools" / "claudelike-1.0.0" / "lib" / "node_modules" / "fixture-claude-like"
            final_bin = (wrapper_dir / "bin" / "claude-like.exe").read_text().strip()
            self.assertEqual(final_bin, "VERIFIED_CONTENT")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_postinstall_binary_check_fails_closed_on_a_mismatch(self):
        # A postinstall that (by bug or tampering) copies from somewhere
        # other than the verified platform dependency must be caught, not
        # silently accepted just because npm rebuild itself exited 0.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wrong_source_dir = tmp_path / "wrong-postinstall-source"
            wrong_source_dir.mkdir()
            package_dir = wrong_source_dir / "claude-like-pkg"
            (package_dir / "bin").mkdir(parents=True)
            (package_dir / "bin" / "claude-like.exe").write_text("STUB\n")
            (package_dir / "postinstall.js").write_text(
                # Deliberately does NOT resolve the platform dependency;
                # copies fixed wrong content instead, mimicking a bug or a
                # tampered lifecycle script that ignores the verified source.
                'const fs = require("fs");\n'
                'const path = require("path");\n'
                'fs.writeFileSync(path.join(__dirname, "bin", "claude-like.exe"), "WRONG_CONTENT\\n");\n'
                'console.log("POSTINSTALL_WROTE_WRONG_CONTENT");\n'
            )
            (package_dir / "package.json").write_text(json.dumps({
                "name": "fixture-claude-like-wrong", "version": "1.0.0",
                "bin": {"claude-like": "bin/claude-like.exe"},
                "optionalDependencies": {"widget-darwin-arm64": f"file:{self.unverified_tarball}"},
                "scripts": {"postinstall": "node postinstall.js"},
            }))
            subprocess.run([NPM, "pack", "--silent", "--pack-destination", str(tmp_path)],
                            cwd=package_dir, capture_output=True, text=True, timeout=60, check=True)
            wrong_tarball = tmp_path / "fixture-claude-like-wrong-1.0.0.tgz"
            wrong_sha256 = hashlib.sha256(wrong_tarball.read_bytes()).hexdigest()

            pins_path = self._pins_fixture(tmp_path, {
                "id": "claudewrong", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/fixture-claude-like-wrong/-/fixture-claude-like-wrong-1.0.0.tgz",
                "sha256": wrong_sha256, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": self._platform_dependency_pin(
                    binary_check={"platform_file": "native-bin", "wrapper_file": "bin/claude-like.exe"}),
            })
            result, eco_root = self._run_install_npm(
                tmp_path, pins_path, "claudewrong", "1.0.0", wrong_tarball, wrong_sha256,
                npm_package="fixture-claude-like-wrong")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("does not match the verified", result.stderr)
            self.assertIn("fail closed", result.stderr)

    def test_fails_closed_on_null_sha256_before_any_fetch_or_npm_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prefix = tmp_path / "tools" / "widget-1.0.0"
            pins_path = self._pins_fixture(tmp_path, {
                "id": "widget", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": {
                    "name": "widget-darwin-arm64", "resolved_package": "widget",
                    "version": "1.0.0-darwin-arm64", "url": "https://example.invalid/never-fetched.tgz",
                    "sha256": None, "integrity": "sha512-unused",
                },
            })
            result = self._run(tmp_path, pins_path, "widget", prefix, 'echo "fetch must not run" >&2; exit 1')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Refusing widget", result.stderr)
            self.assertIn("no verified sha256", result.stderr)
            self.assertFalse(prefix.exists())

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_fails_closed_when_resolved_package_name_does_not_match_the_pin(self):
        # Medium finding: resolved_package is pinned but was not previously
        # read by anything; this checks the extracted package's own
        # package.json "name" against it and fails closed on a mismatch,
        # even though the sha256/version both verified correctly (a real
        # tarball could still be published under a name the pin does not
        # expect, e.g. a registry mixup).
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prefix = tmp_path / "tools" / "widget-1.0.0"
            pins_path = self._pins_fixture(tmp_path, {
                "id": "widget", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
                "sha256": "0" * 64, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": {
                    "name": "widget-darwin-arm64", "resolved_package": "totally-different-package",
                    "version": "1.2.3", "url": "https://example.invalid/verified-platform-dep.tgz",
                    "sha256": self.verified_sha256, "integrity": "sha512-unused-in-this-test",
                },
            })
            result = self._run(tmp_path, pins_path, "widget", prefix,
                                f'cp {json.dumps(str(self.verified_tarball))} "$3"')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Refusing widget", result.stderr)
            self.assertIn("resolved_package is totally-different-package", result.stderr)
            self.assertIn("fixture-real-name", result.stderr)

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
            result = self._run(tmp_path, pins_path, "plain", prefix, 'echo "fetch must not run" >&2; exit 1')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), "")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_a_rerun_into_an_already_populated_prefix_stages_and_swaps_atomically(self):
        # Low finding: re-running install_npm for the same id/version into an
        # already-populated final_prefix would otherwise install directly
        # into a live prefix, leaving a window where the wrapper's freshly
        # updated files point at whatever platform dependency npm's own
        # install just auto-fetched, unverified, before the fix-up runs.
        # Installing into a freshly versioned directory (round 3d: tools/
        # <id>-<version>-<stamp>, never reused) and only then atomically
        # flipping final_prefix (a symlink) onto it means the live
        # final_prefix always resolves to the complete old install or the
        # complete new one. This runs install_npm twice for the same
        # id/version and checks: both succeed, no "*-staged"/"*-link.*"
        # transient survives either run, and the final content is still
        # fully verified after the second (re-)run -- through the SAME
        # stable symlink name both times.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pins_path = self._pins_fixture(tmp_path, {
                "id": "codexlike", "version": "1.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/fixture-codex-like/-/fixture-codex-like-1.0.0.tgz",
                "sha256": self.codex_like_sha256, "checksum_source": "npm_registry_integrity_crosscheck",
                "checksum_ref": "test", "install_note": "test",
                "platform_dependency": self._platform_dependency_pin(),
            })
            first, eco_root = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            final_prefix = eco_root / "tools" / "codexlike-1.0.0"
            self.assertTrue(final_prefix.is_symlink())
            first_target = final_prefix.resolve()
            leftover_links = [p.name for p in (tmp_path / "stage").iterdir() if "-link." in p.name]
            self.assertEqual(leftover_links, [], "no tmp_link may survive a successful run")

            second, eco_root = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like")
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            leftover_links = [p.name for p in (tmp_path / "stage").iterdir() if "-link." in p.name]
            self.assertEqual(leftover_links, [], "no tmp_link may survive the re-run either")
            # The SAME stable symlink name now resolves to a DIFFERENT
            # (newly installed) versioned directory, and the old one is no
            # longer on disk at all -- the flip actually happened, and the
            # previous version's own bytes were cleaned up, not merely
            # orphaned.
            self.assertTrue(final_prefix.is_symlink())
            second_target = final_prefix.resolve()
            self.assertNotEqual(first_target, second_target)
            self.assertFalse(first_target.exists(), "the superseded versioned directory must be cleaned up")

            wrapper_dir = final_prefix / "lib" / "node_modules" / "fixture-codex-like"
            self.assertTrue(wrapper_dir.is_dir())
            content = subprocess.run(
                ["node", "-e",
                 'const p = require.resolve("widget-darwin-arm64/package.json", {paths: [process.argv[1]]});'
                 'const fs = require("fs"), path = require("path");'
                 'process.stdout.write(fs.readFileSync(path.join(path.dirname(p), "native-bin"), "utf8").trim());',
                 str(wrapper_dir)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(content.returncode, 0, content.stdout + content.stderr)
            self.assertEqual(content.stdout.strip(), "VERIFIED_CONTENT")

    def _reinstall_with_previous_target(self, adversarial_target_maker):
        """First install normally, then repoint final_prefix's symlink at an
        adversarial target, then reinstall. adversarial_target_maker(eco_root)
        returns (assertion_path, symlink_target): assertion_path is what the
        test checks survives; symlink_target is what final_prefix.symlink_to
        is actually given (a Path, absolute or relative -- the relative "../"
        case passes a relative one directly, matching a real relative symlink
        target rather than one Python has already resolved to absolute).
        Returns (reinstall_result, eco_root, assertion_path).
        """
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        tmp_path = Path(tmp)
        pins_path = self._codex_like_pins(tmp_path)
        first, eco_root = self._run_install_npm(
            tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
            npm_package="fixture-codex-like")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        final_prefix = eco_root / "tools" / "codexlike-1.0.0"
        self.assertTrue(final_prefix.is_symlink())

        assertion_path, symlink_target = adversarial_target_maker(eco_root)
        final_prefix.unlink()
        final_prefix.symlink_to(symlink_target)

        second, eco_root2 = self._run_install_npm(
            tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
            npm_package="fixture-codex-like")
        return second, eco_root, assertion_path

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_prune_never_deletes_an_external_target(self):
        # Codex round-3e High: previous_versioned (final_prefix's own
        # readlink() text) is unverified and, before this fix, was handed
        # straight to `rm -rf`. An external target -- entirely outside
        # tools/ -- must survive a reinstall untouched.
        def make_external(eco_root):
            external = eco_root.parent / "external-target"
            external.mkdir()
            (external / "sentinel").write_text("do not delete me\n")
            return external, external

        result, eco_root, external = self._reinstall_with_previous_target(make_external)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not pruned for safety", result.stderr)
        self.assertTrue(external.is_dir(), "an external target must never be deleted")
        self.assertEqual((external / "sentinel").read_text(), "do not delete me\n")
        final_prefix = eco_root / "tools" / "codexlike-1.0.0"
        self.assertTrue(final_prefix.is_symlink())
        self.assertNotEqual(final_prefix.resolve(), external.resolve())

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_prune_never_deletes_a_relative_dotdot_target(self):
        # Codex round-3e High: a relative "../" symlink target that resolves
        # OUTSIDE tools/ must be rejected the same way an absolute external
        # target is, not trusted merely because its literal text looks
        # "under" tools/ before resolution.
        def make_dotdot(eco_root):
            outside = eco_root.parent / "outside-via-dotdot"
            outside.mkdir()
            (outside / "sentinel").write_text("do not delete me\n")
            # tools/codexlike-1.0.0 is two levels under eco_root's parent
            # (eco_root/tools/<name>), so "../../outside-via-dotdot" -- a
            # literal relative symlink target, not one Python has already
            # resolved to absolute -- reaches it from there.
            return outside, Path("..") / ".." / "outside-via-dotdot"

        result, eco_root, outside = self._reinstall_with_previous_target(make_dotdot)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not pruned for safety", result.stderr)
        self.assertTrue(outside.is_dir(), "a relative ../ target must never be deleted")
        self.assertEqual((outside / "sentinel").read_text(), "do not delete me\n")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_prune_never_deletes_a_directory_with_a_non_matching_name(self):
        # Codex round-3e High: a target that IS directly under tools/ but
        # whose name does not match "<id>-<version>-<stamp>" (a different
        # tool's own versioned directory, say) must never be deleted either
        # -- being in the right PLACE is not enough on its own.
        def make_wrong_name(eco_root):
            wrong = eco_root / "tools" / "some-other-tool-9.9.9"
            wrong.mkdir()
            (wrong / "sentinel").write_text("do not delete me\n")
            return wrong, wrong

        result, eco_root, wrong = self._reinstall_with_previous_target(make_wrong_name)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not pruned for safety", result.stderr)
        self.assertTrue(wrong.is_dir(), "a non-matching name must never be deleted")
        self.assertEqual((wrong / "sentinel").read_text(), "do not delete me\n")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_prune_never_hangs_or_deletes_on_a_symlink_loop(self):
        # Codex round-3e High: a symlink loop (final_prefix's previous
        # target resolving through a cycle) must never hang canonical_path
        # and must never end up deleting anything -- it simply fails every
        # ownership/name check and is left alone.
        def make_loop(eco_root):
            loop_a = eco_root / "tools" / "loop-a"
            loop_b = eco_root / "tools" / "loop-b"
            loop_a.symlink_to(loop_b)
            loop_b.symlink_to(loop_a)
            return loop_a, loop_a

        result, eco_root, loop_a = self._reinstall_with_previous_target(make_loop)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not pruned for safety", result.stderr)
        self.assertTrue(loop_a.is_symlink(), "a symlink loop's own links must never be deleted")

    def _codex_like_pins(self, tmp_path: Path) -> Path:
        return self._pins_fixture(tmp_path, {
            "id": "codexlike", "version": "1.0.0", "kind": "npm",
            "url": "https://registry.npmjs.org/fixture-codex-like/-/fixture-codex-like-1.0.0.tgz",
            "sha256": self.codex_like_sha256, "checksum_source": "npm_registry_integrity_crosscheck",
            "checksum_ref": "test", "install_note": "test",
            "platform_dependency": self._platform_dependency_pin(),
        })

    def _resolved_content(self, wrapper_dir: Path) -> str:
        content = subprocess.run(
            ["node", "-e",
             'const p = require.resolve("widget-darwin-arm64/package.json", {paths: [process.argv[1]]});'
             'const fs = require("fs"), path = require("path");'
             'process.stdout.write(fs.readFileSync(path.join(path.dirname(p), "native-bin"), "utf8").trim());',
             str(wrapper_dir)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(content.returncode, 0, content.stdout + content.stderr)
        return content.stdout.strip()

    def _downgrade_final_prefix_to_a_real_directory(self, eco_root: Path, final_prefix: Path) -> None:
        """After a normal (round-3d, symlink-based) install, replace
        final_prefix with what a PRE-3d install would have left: a real
        directory holding the same content, not a symlink. Used to exercise
        the one-time migration path (the step table's step 2) a fresh
        install never reaches."""
        target = final_prefix.resolve()
        self.assertTrue(final_prefix.is_symlink(), "expected a round-3d symlink to downgrade")
        final_prefix.unlink()
        target.rename(final_prefix)

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_a_failed_atomic_flip_leaves_final_prefix_exactly_as_it_was(self):
        # Codex round-3d Medium 1, failure injection: the atomic flip's own
        # rename (python3 os.replace) itself fails. final_prefix must be
        # left exactly as it was before this run -- absent (a first
        # install) or still the previous, fully verified symlink target (a
        # reinstall) -- never a broken intermediate state, and the freshly
        # installed (but never made live) versioned directory is simply an
        # orphan, safe to discard.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pins_path = self._codex_like_pins(tmp_path)
            first, eco_root = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            final_prefix = eco_root / "tools" / "codexlike-1.0.0"
            self.assertTrue(final_prefix.is_symlink())
            original_target = final_prefix.resolve()
            wrapper_dir = final_prefix / "lib" / "node_modules" / "fixture-codex-like"
            self.assertEqual(self._resolved_content(wrapper_dir), "VERIFIED_CONTENT")

            # Real python3, except: fails when invoked for the flip's own
            # os.replace one-liner specifically (every other python3 call
            # this script makes -- canonical_path, render_launchd.py, etc.
            # -- is unaffected).
            real_python3 = shutil.which("python3")
            self.assertIsNotNone(real_python3)
            failing_python3_shim = tmp_path / "failing-python3-shim"
            failing_python3_shim.mkdir()
            (failing_python3_shim / "python3").write_text(
                "#!/bin/sh\n"
                'for arg in "$@"; do\n'
                '  case "$arg" in\n'
                "    *os.replace*)\n"
                "      echo 'python3: injected os.replace failure for testing' >&2\n"
                "      exit 1\n"
                "      ;;\n"
                "  esac\n"
                "done\n"
                f'exec {real_python3} "$@"\n'
            )
            (failing_python3_shim / "python3").chmod(0o755)

            second, _ = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like",
                extra_env={"PATH": f"{failing_python3_shim}{os.pathsep}{os.environ['PATH']}"})
            self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("Failed to flip", second.stderr)
            # final_prefix is untouched: still the SAME symlink, to the SAME
            # (original) target, resolving to the SAME verified content.
            self.assertTrue(final_prefix.is_symlink())
            self.assertEqual(final_prefix.resolve(), original_target)
            self.assertEqual(self._resolved_content(wrapper_dir), "VERIFIED_CONTENT")
            # No tmp_link leftover under stage_dir either.
            leftover_links = [p.name for p in (tmp_path / "stage").iterdir() if "-link." in p.name]
            self.assertEqual(leftover_links, [], leftover_links)

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_signal_between_the_one_time_migration_and_the_flip_restores_the_real_directory(self):
        # Codex round-3d Medium 1 / round-3e method (a shared helper looping
        # over steps x signals): a process signaled after the one-time
        # migration (moving a real, pre-3d final_prefix aside) but before
        # the atomic flip completes must not leave final_prefix absent. The
        # top-level cleanup() trap must restore it. Round 3e also explicitly
        # traps INT/TERM/HUP script-wide (not relying on the default,
        # untrapped disposition), so both SIGTERM and SIGINT are exercised
        # here, sent from a shimmed mv exactly at the migration step.
        for signal_name in ("TERM", "INT"):
            with self.subTest(signal=signal_name):
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    pins_path = self._codex_like_pins(tmp_path)
                    first, eco_root = self._run_install_npm(
                        tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                        npm_package="fixture-codex-like")
                    self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                    final_prefix = eco_root / "tools" / "codexlike-1.0.0"
                    self._downgrade_final_prefix_to_a_real_directory(eco_root, final_prefix)
                    self.assertTrue(final_prefix.is_dir() and not final_prefix.is_symlink())
                    wrapper_dir = final_prefix / "lib" / "node_modules" / "fixture-codex-like"
                    original_content = self._resolved_content(wrapper_dir)

                    # Real mv, except: for the migration move specifically
                    # (its DESTINATION is the only "*.migrating.*" path this
                    # script ever names), perform the real move, then send
                    # the signal to the parent script -- simulating a kill
                    # or crash landing exactly between the migration
                    # succeeding and the flip that follows it.
                    signal_mv_shim = tmp_path / f"signal-mv-shim-{signal_name}"
                    signal_mv_shim.mkdir()
                    (signal_mv_shim / "mv").write_text(
                        "#!/bin/sh\n"
                        'dest=""\n'
                        'for arg in "$@"; do dest="$arg"; done\n'
                        'case "$dest" in\n'
                        "  *.migrating.*)\n"
                        '    /bin/mv "$@" || exit $?\n'
                        # Round 3k: was a fixed `kill -SIG "$PPID"; sleep
                        # 0.2; exit 0`, wrong on two counts fixed since --
                        # see _signal_and_wait_for_exit's own docstring for
                        # both. What this line now does: signal
                        # ADOPTION_SCRIPT_PID (never $PPID), then pause
                        # briefly (0.5s, a fixed defensive margin, not a
                        # wait for anything specific) before this shim
                        # itself returns. It does NOT block until the
                        # parent has exited -- this shim is the parent's
                        # own synchronous foreground child, so the parent
                        # cannot exit while still waiting on it; ordering
                        # is guaranteed instead by bash servicing the
                        # pending trap immediately once this shim (its
                        # current foreground child) naturally returns.
                        + _signal_and_wait_for_exit(signal_name, indent="    ")
                        + "    exit 0\n"
                        "    ;;\n"
                        "esac\n"
                        'exec /bin/mv "$@"\n'
                    )
                    (signal_mv_shim / "mv").chmod(0o755)

                    second, _ = self._run_install_npm(
                        tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                        npm_package="fixture-codex-like",
                        extra_env={"PATH": f"{signal_mv_shim}{os.pathsep}{os.environ['PATH']}"})
                    self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
                    # The trap restored the real directory: it exists again,
                    # is still a real directory (not a dangling migrating
                    # name, not absent), and its content is exactly what it
                    # was before.
                    self.assertTrue(final_prefix.is_dir(), "final_prefix must not be left absent after the signal")
                    self.assertFalse(final_prefix.is_symlink(), "the restored copy is the original real directory")
                    self.assertEqual(self._resolved_content(wrapper_dir), original_content)
                    leftover_migrating = [p.name for p in (eco_root / "tools").iterdir() if ".migrating." in p.name]
                    self.assertEqual(leftover_migrating, [], leftover_migrating)

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_a_failed_migration_rollback_keeps_the_previous_copy_and_reports_the_manual_command(self):
        # Codex round-3d Medium 1, failure injection: the flip itself fails
        # (as in the first test above) while a one-time migration is also in
        # progress, AND the trap's own rollback mv also fails. Nothing may
        # be silently lost: the previous, real directory must survive on
        # disk under its "*.migrating.*" name, and the exact manual `mv`
        # command to restore it must be reported.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pins_path = self._codex_like_pins(tmp_path)
            first, eco_root = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            final_prefix = eco_root / "tools" / "codexlike-1.0.0"
            self._downgrade_final_prefix_to_a_real_directory(eco_root, final_prefix)
            wrapper_dir = final_prefix / "lib" / "node_modules" / "fixture-codex-like"
            original_content = self._resolved_content(wrapper_dir)

            real_python3 = shutil.which("python3")
            self.assertIsNotNone(real_python3)
            broken_shim = tmp_path / "broken-shim"
            broken_shim.mkdir()
            # The flip's own os.replace always fails...
            (broken_shim / "python3").write_text(
                "#!/bin/sh\n"
                'for arg in "$@"; do\n'
                '  case "$arg" in\n'
                "    *os.replace*)\n"
                "      echo 'python3: injected os.replace failure for testing' >&2\n"
                "      exit 1\n"
                "      ;;\n"
                "  esac\n"
                "done\n"
                f'exec {real_python3} "$@"\n'
            )
            (broken_shim / "python3").chmod(0o755)
            # ...and so does the trap's own rollback mv (recognized by its
            # SOURCE, the only "*.migrating.*" path this script ever moves
            # FROM).
            (broken_shim / "mv").write_text(
                "#!/bin/sh\n"
                'case "$2" in\n'
                "  *.migrating.*)\n"
                "    echo 'mv: injected rollback failure for testing' >&2\n"
                "    exit 1\n"
                "    ;;\n"
                "esac\n"
                'exec /bin/mv "$@"\n'
            )
            (broken_shim / "mv").chmod(0o755)

            second, _ = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like",
                extra_env={"PATH": f"{broken_shim}{os.pathsep}{os.environ['PATH']}"})
            self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("Restore it manually with: mv --", second.stderr)
            migrating = [p for p in (eco_root / "tools").iterdir() if ".migrating." in p.name]
            self.assertEqual(len(migrating), 1, migrating)
            # The previous copy survives, fully intact, under its migrating
            # name -- nothing was lost, only left exactly where the printed
            # command says to find it.
            migrated_wrapper = migrating[0] / "lib" / "node_modules" / "fixture-codex-like"
            self.assertEqual(self._resolved_content(migrated_wrapper), original_content)
            self.assertIn(migrating[0].name, second.stderr)

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_a_failed_npm_install_leaves_final_prefix_untouched(self):
        # Step 1 (build tree), failure mode: the wrapper's own `npm install`
        # fails outright, before final_prefix (a live symlink from an
        # earlier successful install) is ever referenced. final_prefix must
        # be left exactly as it was: still the same symlink, to the same
        # verified content.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pins_path = self._codex_like_pins(tmp_path)
            first, eco_root = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            final_prefix = eco_root / "tools" / "codexlike-1.0.0"
            self.assertTrue(final_prefix.is_symlink())
            original_target = final_prefix.resolve()
            wrapper_dir = final_prefix / "lib" / "node_modules" / "fixture-codex-like"
            self.assertEqual(self._resolved_content(wrapper_dir), "VERIFIED_CONTENT")

            real_npm = shutil.which("npm")
            self.assertIsNotNone(real_npm)
            failing_npm_shim = tmp_path / "failing-npm-shim"
            failing_npm_shim.mkdir()
            # Real npm, except the wrapper's own top-level `install`
            # subcommand always fails; `npm rebuild` (install_platform_
            # dependency's own, later call) and any version probe are
            # unaffected.
            (failing_npm_shim / "npm").write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "install" ]; then\n'
                "  echo 'npm: injected install failure for testing' >&2\n"
                "  exit 1\n"
                "fi\n"
                f'exec {real_npm} "$@"\n'
            )
            (failing_npm_shim / "npm").chmod(0o755)

            second, _ = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like",
                extra_env={"PATH": f"{failing_npm_shim}{os.pathsep}{os.environ['PATH']}"})
            self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertTrue(final_prefix.is_symlink())
            self.assertEqual(final_prefix.resolve(), original_target)
            self.assertEqual(self._resolved_content(wrapper_dir), "VERIFIED_CONTENT")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_a_signal_during_npm_install_leaves_final_prefix_untouched(self):
        # Step 1 (build tree), signal mode: a signal lands right after the
        # wrapper's own `npm install` completes -- before final_prefix is
        # ever referenced by anything later in install_npm. final_prefix
        # must be left exactly as it was, the same way a failure there does.
        for signal_name in ("TERM", "INT"):
            with self.subTest(signal=signal_name):
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    pins_path = self._codex_like_pins(tmp_path)
                    first, eco_root = self._run_install_npm(
                        tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                        npm_package="fixture-codex-like")
                    self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                    final_prefix = eco_root / "tools" / "codexlike-1.0.0"
                    original_target = final_prefix.resolve()
                    wrapper_dir = final_prefix / "lib" / "node_modules" / "fixture-codex-like"

                    real_npm = shutil.which("npm")
                    self.assertIsNotNone(real_npm)
                    signal_npm_shim = tmp_path / f"signal-npm-{signal_name}-shim"
                    signal_npm_shim.mkdir()
                    (signal_npm_shim / "npm").write_text(
                        "#!/bin/sh\n"
                        'if [ "$1" = "install" ]; then\n'
                        f'  {real_npm} "$@" || exit $?\n'
                        + _signal_and_wait_for_exit(signal_name, indent="  ")
                        + "  exit 0\n"
                        "fi\n"
                        f'exec {real_npm} "$@"\n'
                    )
                    (signal_npm_shim / "npm").chmod(0o755)

                    second, _ = self._run_install_npm(
                        tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                        npm_package="fixture-codex-like",
                        extra_env={"PATH": f"{signal_npm_shim}{os.pathsep}{os.environ['PATH']}"})
                    self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
                    self.assertTrue(final_prefix.is_symlink())
                    self.assertEqual(final_prefix.resolve(), original_target)
                    self.assertEqual(self._resolved_content(wrapper_dir), "VERIFIED_CONTENT")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_a_failed_migration_mv_alone_leaves_the_real_directory_untouched(self):
        # Step 2 (one-time migration), failure mode on its own (not paired
        # with a step-5 flip failure, unlike test_a_failed_migration_
        # rollback... above): the migration mv itself fails before ever
        # moving the real, pre-3d final_prefix aside. final_prefix must be
        # exactly what it was -- still the same real directory, never a
        # dangling ".migrating." name, and cleanup() must not report a
        # phantom pending migration for a move that never actually happened.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pins_path = self._codex_like_pins(tmp_path)
            first, eco_root = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            final_prefix = eco_root / "tools" / "codexlike-1.0.0"
            self._downgrade_final_prefix_to_a_real_directory(eco_root, final_prefix)
            self.assertTrue(final_prefix.is_dir() and not final_prefix.is_symlink())
            wrapper_dir = final_prefix / "lib" / "node_modules" / "fixture-codex-like"
            original_content = self._resolved_content(wrapper_dir)

            failing_migration_mv_shim = tmp_path / "failing-migration-mv-shim"
            failing_migration_mv_shim.mkdir()
            (failing_migration_mv_shim / "mv").write_text(
                "#!/bin/sh\n"
                'dest=""\n'
                'for arg in "$@"; do dest="$arg"; done\n'
                'case "$dest" in\n'
                "  *.migrating.*)\n"
                "    echo 'mv: injected migration failure for testing' >&2\n"
                "    exit 1\n"
                "    ;;\n"
                "esac\n"
                'exec /bin/mv "$@"\n'
            )
            (failing_migration_mv_shim / "mv").chmod(0o755)

            second, _ = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like",
                extra_env={"PATH": f"{failing_migration_mv_shim}{os.pathsep}{os.environ['PATH']}"})
            self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertTrue(final_prefix.is_dir(), "final_prefix must not be left absent")
            self.assertFalse(final_prefix.is_symlink(), "the untouched real directory, not a phantom flip")
            self.assertEqual(self._resolved_content(wrapper_dir), original_content)
            leftover_migrating = [p.name for p in (eco_root / "tools").iterdir() if ".migrating." in p.name]
            self.assertEqual(leftover_migrating, [], leftover_migrating)

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_a_failed_tmp_link_creation_leaves_final_prefix_untouched(self):
        # Step 4 (ln -s tmp_link), failure mode: creating the NEW symlink
        # under stage_dir fails before the atomic os.replace flip is ever
        # attempted. final_prefix must be exactly as it was (absent for a
        # first install; still the previous target for a reinstall).
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pins_path = self._codex_like_pins(tmp_path)
            first, eco_root = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            final_prefix = eco_root / "tools" / "codexlike-1.0.0"
            original_target = final_prefix.resolve()
            wrapper_dir = final_prefix / "lib" / "node_modules" / "fixture-codex-like"

            stage_dir = tmp_path / "stage"
            failing_ln_shim = tmp_path / "failing-ln-shim"
            failing_ln_shim.mkdir()
            (failing_ln_shim / "ln").write_text(
                "#!/bin/sh\n"
                'dest=""\n'
                'for arg in "$@"; do dest="$arg"; done\n'
                f'case "$dest" in\n'
                f"  {stage_dir}/*-link.*)\n"
                "    echo 'ln: injected tmp_link failure for testing' >&2\n"
                "    exit 1\n"
                "    ;;\n"
                "esac\n"
                'exec /bin/ln "$@"\n'
            )
            (failing_ln_shim / "ln").chmod(0o755)

            second, _ = self._run_install_npm(
                tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                npm_package="fixture-codex-like",
                extra_env={"PATH": f"{failing_ln_shim}{os.pathsep}{os.environ['PATH']}"})
            self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertTrue(final_prefix.is_symlink())
            self.assertEqual(final_prefix.resolve(), original_target)
            self.assertEqual(self._resolved_content(wrapper_dir), "VERIFIED_CONTENT")

    @unittest.skipUnless(NPM, "native npm unavailable")
    def test_a_signal_after_creating_tmp_link_leaves_final_prefix_untouched(self):
        # Step 4 (ln -s tmp_link), signal mode: a signal lands right after
        # tmp_link is created but before the atomic os.replace flip ever
        # runs. final_prefix must be exactly as it was; the orphaned
        # tmp_link under stage_dir is inert (nothing live ever reads it).
        for signal_name in ("TERM", "INT"):
            with self.subTest(signal=signal_name):
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    pins_path = self._codex_like_pins(tmp_path)
                    first, eco_root = self._run_install_npm(
                        tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                        npm_package="fixture-codex-like")
                    self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                    final_prefix = eco_root / "tools" / "codexlike-1.0.0"
                    original_target = final_prefix.resolve()
                    wrapper_dir = final_prefix / "lib" / "node_modules" / "fixture-codex-like"

                    stage_dir = tmp_path / "stage"
                    signal_ln_shim = tmp_path / f"signal-ln-{signal_name}-shim"
                    signal_ln_shim.mkdir()
                    (signal_ln_shim / "ln").write_text(
                        "#!/bin/sh\n"
                        'dest=""\n'
                        'for arg in "$@"; do dest="$arg"; done\n'
                        f'case "$dest" in\n'
                        f"  {stage_dir}/*-link.*)\n"
                        '    /bin/ln "$@" || exit $?\n'
                        + _signal_and_wait_for_exit(signal_name, indent="    ")
                        + "    exit 0\n"
                        "    ;;\n"
                        "esac\n"
                        'exec /bin/ln "$@"\n'
                    )
                    (signal_ln_shim / "ln").chmod(0o755)

                    second, _ = self._run_install_npm(
                        tmp_path, pins_path, "codexlike", "1.0.0", self.codex_like_tarball, self.codex_like_sha256,
                        npm_package="fixture-codex-like",
                        extra_env={"PATH": f"{signal_ln_shim}{os.pathsep}{os.environ['PATH']}"})
                    self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
                    self.assertTrue(final_prefix.is_symlink())
                    self.assertEqual(final_prefix.resolve(), original_target)
                    self.assertEqual(self._resolved_content(wrapper_dir), "VERIFIED_CONTENT")

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
                        + _shell_functions(SCRIPT_PATH.read_text(), "canonical_path", "prune_old_version",
                                           "npm_package_name", "install_platform_dependency", "install_npm", "cleanup")
                        + 'pending_migration_prefix=""\n'
                        + 'pending_migration_dest=""\n'
                        + "trap cleanup EXIT\n"
                        + "trap 'exit 130' INT\n"
                        + "trap 'exit 143' TERM\n"
                        + "trap 'exit 129' HUP\n"
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


EMBED_ACCEPTANCE_SCRIPT = ROOT / "tools" / "adoption" / "embed_acceptance.py"
EMBED_REFERENCE_PATH = ROOT / "evidence" / "artifacts" / "macos-embed-reference-20260923" \
    / "macos-embed-reference-20260923.json"


WORKFLOW_PATH = ROOT / ".github" / "workflows" / "adoption-bootstrap.yml"


class CIEmbedModelCacheOrderTests(unittest.TestCase):
    """Round 3i (Codex Medium): the cache restore must run BEFORE
    bootstrap's own checksum verification (a restore running after could
    silently overwrite the just-verified model with stale cached bytes,
    with nothing left to re-check them), and its key must be DERIVED from
    the pin's own sha256, never a literal hardcoded hash string (which
    would keep matching a stale cache entry after the pin itself
    changed)."""

    def setUp(self):
        # PyYAML is optional here, as in tests/test_workflow_hardening.py; the
        # Linux validate job has it, so these structural checks still run in CI.
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; these structural workflow checks run where it is")
        with WORKFLOW_PATH.open() as handle:
            self.workflow = yaml.safe_load(handle)
        self.steps = self.workflow["jobs"]["bootstrap-macos"]["steps"]

    def _step_index(self, name_substring: str) -> int:
        for index, step in enumerate(self.steps):
            if name_substring in step.get("name", ""):
                return index
        self.fail(f"no step with {name_substring!r} in its name")

    def test_the_sha256_read_step_precedes_the_cache_restore(self):
        read_index = self._step_index("Read the pinned embedding model's sha256")
        cache_index = self._step_index("Restore the cached pinned embedding model")
        self.assertLess(read_index, cache_index,
                         "the pin's sha256 must be read before the cache step that keys on it")
        read_step = self.steps[read_index]
        self.assertEqual(read_step.get("id"), "embed-model-pin")
        # Reads the pin file itself, not a hardcoded value.
        self.assertIn("pins-macos-arm64.json", read_step["run"])
        self.assertIn("models[0].sha256", read_step["run"])

    def test_the_cache_restore_precedes_the_bootstrap_step(self):
        cache_index = self._step_index("Restore the cached pinned embedding model")
        bootstrap_index = self._step_index("Run the macOS bootstrap into a disposable prefix")
        self.assertLess(cache_index, bootstrap_index,
                         "restoring the cache after bootstrap's own checksum verification could "
                         "silently overwrite the just-verified model with unverified stale bytes")

    def test_the_cache_key_is_derived_from_the_pin_not_a_literal_hash(self):
        cache_index = self._step_index("Restore the cached pinned embedding model")
        cache_step = self.steps[cache_index]
        self.assertEqual(cache_step["uses"].split("@")[0], "actions/cache")
        key = cache_step["with"]["key"]
        self.assertIn("${{ steps.embed-model-pin.outputs.sha256 }}", key)
        # No literal 64-hex-char sha256 anywhere in the key: a changed pin
        # must always produce a different, freshly-derived key.
        self.assertIsNone(re.search(r"(?<![{}.a-zA-Z0-9])[0-9a-f]{64}(?![0-9a-f])", key), key)
        # The cache step's own PATH must still be the exact destination
        # install_embed_model (adoption/bootstrap-macos.sh) writes to.
        self.assertEqual(
            cache_step["with"]["path"],
            "${{ runner.temp }}/eco/state/models/embeddinggemma-300M-Q8_0.gguf",
        )

    def test_only_one_cache_step_exists_not_a_leftover_duplicate(self):
        cache_steps = [step for step in self.steps if "Cache the pinned embedding model" in step.get("name", "")
                       or "Restore the cached pinned embedding model" in step.get("name", "")]
        self.assertEqual(len(cache_steps), 1, cache_steps)

    def test_bootstrap_re_verifies_any_cached_file_via_fetch(self):
        # Confirms the invariant the step ordering above depends on:
        # install_embed_model (called unconditionally by bootstrap-macos.sh)
        # routes through fetch(), whose own existing-destination check is a
        # checksum match, not a bare existence check -- so a cache restore
        # that lands a WRONG file at the destination is transparently
        # re-downloaded and re-verified, on the exact same path a genuine
        # cache miss already takes, never silently trusted.
        text = SCRIPT_PATH.read_text()
        fetch_body = re.search(r"(?ms)^fetch\(\) \{\n.*?^\}\n", text)
        self.assertIsNotNone(fetch_body, "fetch() not found")
        self.assertIn('shasum -a 256 --check --status', fetch_body.group(0))
        self.assertIn("install_embed_model", text)


class CIRecordingToolingSmokeTests(unittest.TestCase):
    """Round 3i (2026-09-23 peer-update-audit gap, adoption_macos, medium):
    the catalog's own recording and verdict scripts had never run on macOS
    CI or against macOS's own system Python. Structural checks only -- the
    steps themselves only ever run on a real macos-15 runner; see
    adoption/platforms/macos-arm64.md's "Recording and verdict scripts"."""

    def setUp(self):
        # PyYAML is optional in this repository (tests/test_workflow_hardening.py
        # skips the same way): the setup-python interpreter on the macos-15
        # validate job has no PyYAML, while the Linux validate job does, so these
        # structural checks still run in CI there.
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; these structural workflow checks run where it is")
        with WORKFLOW_PATH.open() as handle:
            self.workflow = yaml.safe_load(handle)
        self.steps = self.workflow["jobs"]["validate-macos"]["steps"]

    def _step_index(self, name_substring: str) -> int:
        for index, step in enumerate(self.steps):
            if name_substring in step.get("name", ""):
                return index
        self.fail(f"no step with {name_substring!r} in its name")

    def test_every_recording_and_verdict_script_is_gated(self):
        run_text = "\n".join(step.get("run", "") for step in self.steps)
        for expected in (
            "scripts/host_receipts.py validate",
            "scripts/component_matrix.py --check",
            "scripts/new_host_grand_list.py --check",
            "tools/sota-convergence/build_verdicts.py --check",
            "scripts/validate_convergence.py --all-recorded",
            "scripts/release_due.py",
        ):
            self.assertIn(expected, run_text, expected)

    def test_release_due_is_report_only_never_strict(self):
        step = self.steps[self._step_index(
            "Report any new-machine paths main documents but the pinned release lacks")]
        self.assertNotIn("--strict", step["run"])

    def test_bootstrap_precedes_the_recording_smoke(self):
        bootstrap_index = self._step_index("Run the macOS bootstrap into a disposable prefix "
                                            "(recording-script smoke)")
        smoke_index = self._step_index("Recording smoke: record a real receipt")
        self.assertLess(bootstrap_index, smoke_index)

    def test_the_recording_smoke_uses_a_throwaway_copy_never_the_real_checkout(self):
        step = self.steps[self._step_index("Recording smoke: record a real receipt")]
        run_text = step["run"]
        self.assertIn("rec_dir=\"$RUNNER_TEMP/rec\"", run_text)
        self.assertIn("rm -rf \"$rec_dir\"", run_text)
        # host_receipts.py record/component_matrix.py --write/new_host_grand_
        # list.py --write all run with cwd inside $rec_dir, never $GITHUB_
        # WORKSPACE -- the subshell `cd "$rec_dir"` wrapping them is what
        # keeps every write there, never in the real checkout.
        self.assertIn('cd "$rec_dir"', run_text)

    def test_the_recording_smoke_uses_native_proven_and_a_valid_host_id(self):
        step = self.steps[self._step_index("Recording smoke: record a real receipt")]
        run_text = step["run"]
        self.assertIn("--evidence-class native_proven", run_text)
        self.assertIn("--from-stack-commands", run_text)
        host_id_match = re.search(r"--host-id\s+([A-Za-z0-9-]+)", run_text)
        self.assertIsNotNone(host_id_match, "no --host-id found")
        # scripts/host_receipts.py's own HOST_ID_PATTERN: lowercase/digits/
        # hyphens, ending in an 8-digit date.
        self.assertRegex(host_id_match.group(1), r"^[a-z0-9-]+-[0-9]{8}$")

    def test_the_recording_smoke_runs_against_both_pinned_and_system_python(self):
        step = self.steps[self._step_index("Recording smoke: record a real receipt")]
        run_text = step["run"]
        self.assertIn('run_smoke python3 "the manifest-pinned Python line', run_text)
        self.assertIn("/usr/bin/python3", run_text)
        self.assertIn("meets_min", run_text)
        # A below-minimum system Python is skipped, not failed.
        self.assertIn("skipping the system-Python recording smoke", run_text)

    def test_the_minimum_python_version_is_39_everywhere_it_is_declared(self):
        step = self.steps[self._step_index("Recording smoke: record a real receipt")]
        self.assertIn('min_version="3.9"', step["run"])
        for doc_path in (ROOT / "adoption" / "bootstrap.md", PAGE_PATH):
            text = doc_path.read_text()
            self.assertIn("Python 3.9", text, doc_path)


class CIWorkflowTriggerPathsTests(unittest.TestCase):
    """Round 3j (Codex P2 thread 6): the push paths trigger must include every
    input the macOS jobs actually consume, not just adoption/** and
    tools/adoption/** -- a change to, say, scripts/host_receipts.py would
    otherwise never re-run this workflow at all on push, even though
    validate-macos's recording-tooling gate and recording smoke both depend
    on it directly.

    2026-09-25 (validate-macos required-check readiness,
    docs/decisions/2026-09-22-github-automation-closure.md, "validate-macos
    required (2026-09-25)"): pull_request no longer has its own `paths:`
    filter at all -- a required check must report a status on every PR, and
    a path-filtered one cannot. The `changes` job now reproduces the same
    path membership test for pull_request with plain git, and its own
    pattern list is asserted to match `push`'s `paths:` list in
    tests.test_workflow_hardening.AdoptionBootstrapMacosRequiredTests
    (that assertion lives there, not duplicated here, since it needs the
    text parser for the job's embedded shell script, not YAML)."""

    def setUp(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; these structural workflow checks run where it is")
        with WORKFLOW_PATH.open() as handle:
            self.workflow = yaml.safe_load(handle)
        # "on" is a YAML 1.1 boolean keyword; PyYAML's SafeLoader parses
        # the bare "on:" key as the Python value True, not the string "on".
        self.triggers = self.workflow[True]

    def test_every_macos_job_input_is_a_push_trigger_path(self):
        for expected in (
            "evidence/artifacts/macos-embed-reference-20260923/**",
            "scripts/host_receipts.py",
            "scripts/component_matrix.py",
            "scripts/new_host_grand_list.py",
            "tools/sota-convergence/build_verdicts.py",
            "scripts/platform_status.py",
            "scripts/validate_convergence.py",
            "scripts/release_due.py",
            "scripts/landscape.py",
            "manifests/evidence.json",
        ):
            self.assertIn(expected, self.triggers["push"]["paths"], expected)

    def test_pull_request_trigger_has_no_path_filter(self):
        # A bare `pull_request:` key with no mapping parses as None; that
        # emptiness is exactly what makes validate-macos reachable on every
        # pull request (the required-check readiness this change makes).
        self.assertIsNone(self.triggers["pull_request"])


class EmbedAcceptanceScriptTests(unittest.TestCase):
    """tools/adoption/embed_acceptance.py (round 3h) against a local stdlib
    HTTP server standing in for llama-server, and the real, committed
    reference vector -- never a live network call, and never a claim that
    a real llama-server produced any of these responses."""

    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(EMBED_REFERENCE_PATH.read_text())

    def _serve(self, response_body: bytes, status: int = 200):
        import http.server
        import threading

        reference = self.reference

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 (BaseHTTPRequestHandler's own naming)
                length = int(self.headers.get("Content-Length", 0))
                sent = json.loads(self.rfile.read(length)) if length else {}
                if sent != reference["request"]["body"]:
                    self.send_response(400)
                    self.end_headers()
                    return
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _run(self, url: str, extra_args: list[str] | None = None):
        return subprocess.run(
            [sys.executable, str(EMBED_ACCEPTANCE_SCRIPT), url, str(EMBED_REFERENCE_PATH), *(extra_args or [])],
            capture_output=True, text=True, timeout=30,
        )

    def test_the_exact_reference_embedding_passes_with_cosine_1(self):
        # The identical request body is asserted server-side (_serve above
        # returns 400 on any mismatch), directly proving this script sends
        # the EXACT body the reference recorded, not an approximation.
        body = json.dumps({"data": [{"embedding": self.reference["embedding"], "index": 0}]}).encode()
        url = self._serve(body)
        result = self._run(url)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["cosine"], 1.0)
        self.assertEqual(payload["dimension_actual"], self.reference["dimension"])

    def test_native_llama_cpp_embedding_shape_is_also_understood(self):
        # llama.cpp's native /embedding response (not /v1/embeddings, but
        # exercised here for the shape: a list of objects, each embedding
        # itself one row per pooled token) nests one level deeper than the
        # OpenAI-compatible shape; extract_embedding must unwrap either.
        body = json.dumps([{"embedding": [self.reference["embedding"]]}]).encode()
        url = self._serve(body)
        result = self._run(url)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["passed"])

    def test_a_dimension_mismatch_fails_with_a_clear_json_error(self):
        body = json.dumps({"data": [{"embedding": [0.1, 0.2, 0.3]}]}).encode()
        url = self._serve(body)
        result = self._run(url)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["passed"])
        self.assertEqual(payload["dimension_actual"], 3)
        self.assertIn("dimension mismatch", payload["error"])

    def test_a_low_cosine_fails_even_with_the_right_dimension(self):
        # A different, but same-dimension, vector: cosine similarity to the
        # reference is well below the 0.99 threshold.
        wrong = [0.0] * self.reference["dimension"]
        wrong[0] = 1.0
        body = json.dumps({"data": [{"embedding": wrong}]}).encode()
        url = self._serve(body)
        result = self._run(url)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["passed"])
        self.assertLess(payload["cosine"], 0.99)

    def test_a_connection_failure_reports_json_not_a_traceback(self):
        result = self._run("http://127.0.0.1:1", extra_args=["--timeout", "2"])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "", "a network failure must be a reported JSON result, not a traceback")
        payload = json.loads(result.stdout)
        self.assertFalse(payload["passed"])
        self.assertIn("error", payload)

    def test_reference_artifact_matches_the_pinned_model_and_is_registered_evidence(self):
        model = json.loads(PINS_PATH.read_text())["models"][0]
        self.assertEqual(self.reference["model"]["sha256"], model["sha256"])
        self.assertEqual(self.reference["model"]["hf_revision"], model["hf_revision"])
        self.assertEqual(self.reference["dimension"], 768)
        self.assertEqual(self.reference["acceptance"]["threshold"], 0.99)

    def _raw_socket_server(self, handle_connection):
        """A minimal raw-socket TCP server for transport-level failure
        modes http.server.BaseHTTPRequestHandler cannot easily produce
        (an incomplete body relative to its own declared Content-Length,
        or a stall mid-body): `handle_connection(conn)` gets the accepted
        connection and is responsible for reading the request and writing
        whatever raw bytes it wants, then closing (or not) the socket
        itself."""
        import socket
        import threading

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("127.0.0.1", 0))
        server_socket.listen(1)
        port = server_socket.getsockname()[1]

        def serve_once():
            try:
                conn, _ = server_socket.accept()
            except OSError:
                return
            try:
                handle_connection(conn)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

        thread = threading.Thread(target=serve_once, daemon=True)
        thread.start()
        self.addCleanup(server_socket.close)
        return f"http://127.0.0.1:{port}"

    @staticmethod
    def _drain_http_request(conn):
        """Read the whole request (headers, then Content-Length body bytes).
        A single recv() can return only part of it; closing a socket with
        unread request bytes makes the kernel send RST instead of FIN, so the
        client sees ECONNRESET rather than the IncompleteRead under test."""
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(65536)
            if not chunk:
                return
            data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        length = 0
        for line in head.split(b"\r\n")[1:]:
            name, _, value = line.partition(b":")
            if name.strip().lower() == b"content-length":
                length = int(value.strip() or 0)
        while len(body) < length:
            chunk = conn.recv(65536)
            if not chunk:
                return
            body += chunk

    def test_an_incomplete_response_body_reports_json_not_a_traceback(self):
        # Round 3i (Codex Low): the server declares Content-Length: 1000
        # but sends only a handful of body bytes, then closes the
        # connection -- http.client.IncompleteRead, which the pre-fix
        # except clause (urllib.error.URLError only) did not catch,
        # leaving stdout empty and the process exiting via an uncaught
        # traceback instead of the documented JSON failure contract.
        import socket

        def handle(conn):
            self._drain_http_request(conn)  # its content is irrelevant here
            conn.sendall(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 1000\r\n"
                b"\r\n"
                b'{"data"'
            )
            # Half-close (FIN, not RST) well short of the promised 1000
            # bytes; the `finally` in _raw_socket_server then closes.
            conn.shutdown(socket.SHUT_WR)

        url = self._raw_socket_server(handle)
        result = self._run(url, extra_args=["--timeout", "5"])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "",
                          "an incomplete response must be a reported JSON result, not a traceback")
        payload = json.loads(result.stdout)
        self.assertFalse(payload["passed"])
        self.assertIn("incomplete", payload["error"])

    def test_a_stalled_response_body_times_out_and_reports_json_not_a_traceback(self):
        # Round 3i (Codex Low): the server sends valid headers (urlopen's
        # own connect-phase succeeds) and a partial body, then stalls
        # indefinitely without closing the connection -- a bare
        # TimeoutError from response.read() itself, past urlopen's own
        # initial connection, which URLError alone did not catch.
        import time

        def handle(conn):
            self._drain_http_request(conn)
            conn.sendall(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 1000\r\n"
                b"\r\n"
                b'{"data"'
            )
            time.sleep(5)  # far longer than this test's own --timeout

        url = self._raw_socket_server(handle)
        result = self._run(url, extra_args=["--timeout", "1"])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "",
                          "a stalled response must be a reported JSON result, not a traceback")
        payload = json.loads(result.stdout)
        self.assertFalse(payload["passed"])
        self.assertIn("timed out", payload["error"])


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
