"""Offline Linux integration checks ported from the macOS platform-dependency tests.

Real npm installs local fixture tarballs offline. Logging shims inject package
placement and publication failures; the shipped guards, Node resolution,
rebuild and publication paths actually run.
These are local integration checks, not upstream tests or a native Codex run.
"""

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

from tests.test_adoption_bootstrap import SCRIPT_PATH, load_pins, shell_functions


NPM = shutil.which("npm")
NODE = shutil.which("node")
PYTHON = shutil.which("python3")
BINARY_PATH = "vendor/x86_64-unknown-linux-musl/bin/codex"
VERIFIED_BINARY = b"#!/bin/sh\nprintf 'VERIFIED_PLATFORM_BINARY\\n'\n"


class LinuxPlatformPinTests(unittest.TestCase):
    def test_codex_pins_the_registry_alias_archive_and_native_binary(self):
        pin = next(tool for tool in load_pins()["tools"] if tool["id"] == "codex")
        self.assertIs(pin["ignore_scripts"], True)
        dep = pin["platform_dependency"]
        self.assertEqual(dep["name"], "@openai/codex-linux-x64")
        self.assertEqual(dep["resolved_package"], "@openai/codex")
        self.assertEqual(dep["version"], pin["version"] + "-linux-x64")
        self.assertEqual(dep["url"],
                         f"https://registry.npmjs.org/@openai/codex/-/codex-{dep['version']}.tgz")
        self.assertEqual(dep["sha256"],
                         "37a41d61c3399182b8c727b77090cc7a1566bd849d0f09070a0bbc6fec4c58dc")
        self.assertEqual(dep["integrity"],
                         "sha512-KI/73OqGrHmR18s7ya7E1NqV6rT0y3lxr0s8S1qR2m6zU6QRF/HlR529jALLh5vjdUnsRT4Ahoxt0axb4kY99g==")
        self.assertEqual(dep["installed_binary_check"], {
            "path": BINARY_PATH,
            "sha256": "12eb3e81114588aca3b7998f4f19e8997b056aca08e57a7ca7c8a3ec8c652aad",
        })


@unittest.skipUnless(NPM and shutil.which("node") and shutil.which("jq"),
                     "native npm, node and jq required for offline integration checks")
class LinuxPlatformDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.npm_env = {
            **os.environ, "npm_config_offline": "true",
            "npm_config_cache": str(root / "npm-cache"),
            "npm_config_userconfig": str(root / "empty-npmrc"),
            "npm_config_globalconfig": str(root / "empty-global-npmrc"),
            "npm_config_allow_scripts": "fixture-wrapper",
        }
        (root / "empty-npmrc").touch()
        (root / "empty-global-npmrc").touch()

        def pack(name, manifest, binary, executable=True):
            directory = root / name
            directory.mkdir()
            (directory / "package.json").write_text(json.dumps(manifest))
            native = directory / BINARY_PATH
            native.parent.mkdir(parents=True)
            native.write_bytes(binary)
            native.chmod(0o755 if executable else 0o644)
            auxiliary = directory / "vendor/x86_64-unknown-linux-musl/bin/codex-code-mode-host"
            auxiliary.write_bytes(VERIFIED_BINARY)
            auxiliary.chmod(0o755)
            result = subprocess.run(
                [NPM, "pack", "--offline", "--ignore-scripts", "--silent",
                 "--pack-destination", str(directory)],
                cwd=directory, env=cls.npm_env, capture_output=True, text=True,
                timeout=60, check=True,
            )
            return directory / result.stdout.strip().splitlines()[-1]

        manifest = {"name": "fixture-platform", "version": "1.2.3"}
        cls.verified = pack("verified", manifest, VERIFIED_BINARY)
        cls.unverified = pack("unverified", manifest,
                              b"#!/bin/sh\nprintf 'UNVERIFIED_PLATFORM_BINARY\\n'\n")
        cls.wrong_identity = pack("wrong-identity",
                                  {"name": "wrong-package", "version": "1.2.3"}, VERIFIED_BINARY)
        cls.wrong_version = pack("wrong-version",
                                 {"name": "fixture-platform", "version": "9.9.9"}, VERIFIED_BINARY)
        cls.nonexecutable = pack("nonexecutable", manifest, VERIFIED_BINARY, executable=False)
        cls.no_binary = pack("no-binary", manifest, VERIFIED_BINARY)
        # A fixture lacking the native executable, packed by npm itself.
        (root / "no-binary" / BINARY_PATH).unlink()
        cls.no_binary = pack_existing(root / "no-binary", cls.npm_env)

        cls.wrappers = {}
        for variant in ("runtime", "alias", "wrong-dependency", "missing-dependency",
                        "corrupt-rebuild", "corrupt-auxiliary", "corrupt-mode", "rebuild-extra-package"):
            directory = root / variant
            (directory / "bin").mkdir(parents=True)
            launcher_dep = "different-linux-x64" if variant == "wrong-dependency" else "fixture-linux-x64"
            (directory / "bin" / "widget.js").write_text(
                '#!/usr/bin/env node\n'
                'const path = require("path");\n'
                f'const root = path.dirname(require.resolve("{launcher_dep}/package.json"));\n'
                f'const result = require("child_process").spawnSync(path.join(root, "{BINARY_PATH}"), '
                'process.argv.slice(2), {stdio: "inherit"});\n'
                'process.exit(result.status === null ? 1 : result.status);\n'
            )
            (directory / "bin" / "widget.js").chmod(0o755)
            wrapper = {"name": "fixture-wrapper", "version": "1.0.0",
                       "bin": {"widget": "bin/widget.js"}}
            if variant != "missing-dependency":
                wrapper["optionalDependencies"] = {launcher_dep: "npm:fixture-platform@1.2.3"}
            if variant in ("corrupt-rebuild", "corrupt-auxiliary", "corrupt-mode", "rebuild-extra-package"):
                corrupt_path = (BINARY_PATH if variant == "corrupt-rebuild" else
                                "vendor/x86_64-unknown-linux-musl/bin/codex-code-mode-host")
                mutation = (f'fs.writeFileSync(path.join(root, "{corrupt_path}"), "CORRUPTED\\n");\n'
                            if variant != "rebuild-extra-package" else
                            'fs.mkdirSync(path.join(__dirname, "node_modules", "decoy"), {recursive: true});\n')
                if variant == "corrupt-mode":
                    mutation = f'fs.chmodSync(path.join(root, "{corrupt_path}"), 0o644);\n'
                (directory / "corrupt.js").write_text(
                    'const fs = require("fs"), path = require("path");\n'
                    'const root = path.dirname(require.resolve("fixture-linux-x64/package.json"));\n'
                    + mutation
                )
                wrapper["scripts"] = {"postinstall": "node corrupt.js"}
            (directory / "package.json").write_text(json.dumps(wrapper))
            cls.wrappers[variant] = pack_existing(directory, cls.npm_env)

        archive = cls.verified.read_bytes()
        cls.dep = {
            "name": "fixture-linux-x64", "resolved_package": "fixture-platform", "version": "1.2.3",
            "url": "https://example.invalid/verified-platform.tgz",
            "sha256": hashlib.sha256(archive).hexdigest(),
            "integrity": "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode(),
            "installed_binary_check": {"path": BINARY_PATH,
                                       "sha256": hashlib.sha256(VERIFIED_BINARY).hexdigest()},
        }

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_install(self, root, *, dep=None, variant="runtime", archive=None, previous=False,
                    ignore_scripts="false", injection="", failed_swap=False,
                    prune_failure=False, collision=False, previous_is_new=False,
                    pythonpath=False, nodepath=False):
        eco = root / "eco"
        for child in ("downloads", "tools", "bin", "staging.fixture"):
            (eco / child).mkdir(parents=True)
        if previous:
            (eco / "tools" / "widget-1.0.0").mkdir()
            (eco / "tools" / "widget-1.0.0" / "prior").write_text("keep prior install\n")
        wrapper_archive = self.wrappers[variant]
        wrapper_url = "https://registry.npmjs.org/fixture-wrapper/-/fixture-wrapper-1.0.0.tgz"
        pin = {
            "id": "widget", "version": "1.0.0", "kind": "npm", "url": wrapper_url,
            "sha256": hashlib.sha256(wrapper_archive.read_bytes()).hexdigest(),
            "platform_dependency": copy.deepcopy(self.dep if dep is None else dep),
        }
        pins_path = root / "pins.json"
        pins_path.write_text(json.dumps({"tools": [pin]}))
        shim = root / "shim"
        shim.mkdir()
        # Keep fetch() intact: curl serves only these local archives, and npm
        # runs offline with an isolated cache and empty config files.
        (shim / "curl").write_text(
            '#!/bin/sh\nurl=""; out=""; prev=""\n'
            'for arg in "$@"; do\n'
            '  [ "$prev" = "--output" ] && out="$arg"\n'
            '  case "$arg" in https://*) url="$arg" ;; esac\n'
            '  prev="$arg"\ndone\ncase "$url" in\n'
            f'  {shlex.quote(wrapper_url)}) cp {shlex.quote(str(wrapper_archive))} "$out" ;;\n'
            f'  https://example.invalid/verified-platform.tgz) cp {shlex.quote(str(archive or self.verified))} "$out" ;;\n'
            '  *) echo "unexpected network URL" >&2; exit 1 ;;\nesac\n'
        )
        (shim / "curl").chmod(0o755)
        # npm cannot resolve the fixture's registry alias from its empty offline
        # cache. Native npm still installs the actual wrapper; this shim then
        # injects the unverified nested copy whose placement the guard must bind.
        wrapper_dir = '"$prefix/lib/node_modules/fixture-wrapper"'
        nested_name = "different-linux-x64" if variant == "wrong-dependency" else "fixture-linux-x64"
        nested = f'"$prefix/lib/node_modules/fixture-wrapper/node_modules/{nested_name}"'
        placement = ""
        if variant != "alias":
            placement = (f'mkdir -p {nested}\n'
                         f'tar -xzf {shlex.quote(str(self.unverified))} --strip-components=1 -C {nested}\n')
        if injection == "extra-nested":
            placement += f'mkdir -p {wrapper_dir}/node_modules/decoy\n'
        elif injection == "extra-global":
            placement += 'mkdir -p "$prefix/lib/node_modules/decoy"\n'
        elif injection in ("existing-alias", "outside-alias"):
            destination = '"$prefix/lib/node_modules/fixture-linux-x64"'
            if injection == "existing-alias":
                placement += f'mkdir -p {destination}\n'
            else:
                outside = root / "outside"
                outside.mkdir()
                (outside / "sentinel").write_text("must survive\n")
                placement += f'ln -s {shlex.quote(str(outside))} {destination}\n'
        (shim / "npm").write_text(
            '#!/bin/bash\nset -e\nprintf "%s\\n" "$*" >> ' + shlex.quote(str(root / "npm.log")) + '\n'
            + shlex.quote(NPM) + ' "$@"\n'
            + 'if [[ "$1" == install ]]; then\n'
            + '  prefix=""; prev=""\n  for arg in "$@"; do\n'
            + '    [[ "$prev" != --prefix ]] || prefix="$arg"\n    prev="$arg"\n  done\n'
            + placement + 'fi\n'
        )
        (shim / "npm").chmod(0o755)
        (shim / "mv").write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> ' + shlex.quote(str(root / "mv.log"))
            + '\nexec ' + shlex.quote(shutil.which("mv")) + ' "$@"\n'
        )
        (shim / "mv").chmod(0o755)
        if failed_swap:
            (shim / "python3").write_text(
                '#!/bin/sh\ncase "$*" in *os.replace*) exit 73 ;; esac\nexec '
                + shlex.quote(PYTHON) + ' "$@"\n'
            )
            (shim / "python3").chmod(0o755)
        if prune_failure:
            (shim / "rm").write_text(
                '#!/bin/sh\ncase "$*" in *.migrating.*) exit 74 ;; esac\nexec '
                + shlex.quote(shutil.which("rm")) + ' "$@"\n'
            )
            (shim / "rm").chmod(0o755)
        if collision or previous_is_new:
            (shim / "date").write_text('#!/bin/sh\nprintf "fixed\\n"\n')
            (shim / "date").chmod(0o755)
        source = SCRIPT_PATH.read_text()
        names = ("verify_sha256", "fetch", "fetch_platform_dependency", "verify_platform_packages",
                 "canonical_path", "prune_old_version",
                 "npm_package_name", "install_platform_dependency", "install_npm", "cleanup")
        # Allows the pre-fix script to run the same regression against the
        # actual vulnerable install_npm, rather than failing during extraction.
        names = tuple(name for name in names if f"\n{name}() {{" in source)
        harness = root / "install.sh"
        harness.write_text(
            "set -Eeuo pipefail\n" + shell_functions(source, *names)
            + f"pins_path={shlex.quote(str(pins_path))}\n"
            + f"ecosystem_root={shlex.quote(str(eco))}\n"
            + f"bin_dir={shlex.quote(str(eco / 'bin'))}\n"
            + f"cache_dir={shlex.quote(str(eco / 'downloads'))}\n"
            + f"stage_dir={shlex.quote(str(eco / 'staging.fixture'))}\n"
            + 'pending_migration_prefix=""\npending_migration_dest=""\n'
            + 'unpublished_prefix=""\nunpublished_dest=""\n'
            + "trap cleanup EXIT\ntrap 'exit 130' INT\ntrap 'exit 143' TERM\ntrap 'exit 129' HUP\n"
            + ('mkdir "$ecosystem_root/tools/widget-1.0.0-fixed-$$"\n'
               'printf "collision survives\\n" > "$ecosystem_root/tools/widget-1.0.0-fixed-$$/sentinel"\n'
               if collision else '')
            + ('ln -s "$ecosystem_root/tools/widget-1.0.0-fixed-$$" "$ecosystem_root/tools/widget-1.0.0"\n'
               if previous_is_new else '')
            + f"install_npm widget 1.0.0 {shlex.quote(wrapper_url)} {pin['sha256']} {ignore_scripts}\n"
        )
        env = {**self.npm_env, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}
        if pythonpath:
            poison = root / "poison"
            poison.mkdir()
            (poison / "hashlib.py").write_text('raise RuntimeError("PYTHONPATH must be ignored")\n')
            env["PYTHONPATH"] = str(poison)
        if nodepath:
            decoy = root / "decoy" / "fixture-linux-x64"
            decoy.mkdir(parents=True)
            subprocess.run(["tar", "-xzf", str(self.unverified), "--strip-components=1", "-C", str(decoy)],
                           timeout=10, check=True)
            env["NODE_PATH"] = str(decoy.parent)
        result = subprocess.run(["bash", str(harness)], capture_output=True, text=True,
                                timeout=60, env=env)
        return result, eco

    def test_matching_dependency_replaces_npm_shadow_before_linking(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, eco = self.run_install(Path(tmp))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            binary = eco / "tools/widget-1.0.0/lib/node_modules/fixture-wrapper/node_modules/fixture-linux-x64" / BINARY_PATH
            self.assertEqual(binary.read_bytes(), VERIFIED_BINARY)
            executed = subprocess.run([str(eco / "bin/widget")], capture_output=True, text=True, timeout=10)
            self.assertEqual((executed.returncode, executed.stdout), (0, "VERIFIED_PLATFORM_BINARY\n"))

    def test_sha256_mismatch_fails_without_publishing(self):
        self.assert_refused({**self.dep, "sha256": "0" * 64}, "Checksum mismatch")

    def test_integrity_mismatch_fails_without_publishing(self):
        self.assert_refused({**self.dep, "integrity": "sha512-" + base64.b64encode(b"wrong digest").decode()},
                            "Refusing widget: platform dependency fixture-linux-x64 integrity mismatch (fail closed).",
                            previous=True, before_npm=True)

    def test_missing_integrity_fails_closed(self):
        dep = copy.deepcopy(self.dep)
        del dep["integrity"]
        self.assert_refused(dep, "no supported sha512 integrity pin", previous=True, before_npm=True)

    def test_missing_dependency_metadata_fails_closed(self):
        dep = copy.deepcopy(self.dep)
        del dep["sha256"]
        self.assert_refused(dep, "no verified sha256")

    def test_missing_dependency_from_npm_is_installed_as_verified_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, eco = self.run_install(Path(tmp), variant="alias")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            binary = eco / "tools/widget-1.0.0/lib/node_modules/fixture-linux-x64" / BINARY_PATH
            self.assertEqual(binary.read_bytes(), VERIFIED_BINARY)
            self.assert_verified_launcher(eco)

    def test_wrapper_optional_dependency_key_mismatch_never_runs_unverified_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, eco = self.run_install(Path(tmp), variant="wrong-dependency", previous=True)
            launcher = eco / "bin/widget"
            if launcher.exists():
                executed = subprocess.run([str(launcher)], capture_output=True, text=True, timeout=10)
                self.assertNotIn("UNVERIFIED_PLATFORM_BINARY", executed.stdout)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("optionalDependencies", result.stderr)
            self.assert_failed_state(Path(tmp), eco, previous=True)

    def test_missing_wrapper_mapping_fails_closed(self):
        self.assert_refused(self.dep, "optionalDependencies", variant="missing-dependency")

    def test_unexpected_nested_and_global_packages_fail_closed(self):
        for injection in ("extra-nested", "extra-global"):
            with self.subTest(injection=injection):
                self.assert_refused(self.dep, "unexpected package", injection=injection)

    def test_alias_target_must_be_new_and_inside_prefix(self):
        for injection in ("existing-alias", "outside-alias"):
            with self.subTest(injection=injection):
                self.assert_refused(self.dep, "alias target", variant="alias", injection=injection)

    def test_node_path_decoy_is_untouched_and_verified_alias_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, eco = self.run_install(root, variant="alias", nodepath=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assert_verified_launcher(eco)
            self.assertIn(b"UNVERIFIED_PLATFORM_BINARY", (root / "decoy/fixture-linux-x64" / BINARY_PATH).read_bytes())

    def test_sha512_ignores_pythonpath(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, eco = self.run_install(Path(tmp), pythonpath=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assert_verified_launcher(eco)

    def test_installed_binary_hash_mismatch_preserves_previous_install(self):
        dep = copy.deepcopy(self.dep)
        dep["installed_binary_check"]["sha256"] = "0" * 64
        self.assert_refused(dep, "installed binary", previous=True)

    def test_missing_installed_binary_fails_closed(self):
        dep = copy.deepcopy(self.dep)
        payload = self.no_binary.read_bytes()
        dep["sha256"] = hashlib.sha256(payload).hexdigest()
        dep["integrity"] = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode()
        self.assert_refused(dep, "installed binary", archive=self.no_binary)

    def test_wrong_package_identity_fails_closed(self):
        dep = copy.deepcopy(self.dep)
        payload = self.wrong_identity.read_bytes()
        dep["sha256"] = hashlib.sha256(payload).hexdigest()
        dep["integrity"] = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode()
        self.assert_refused(dep, "package.json name", archive=self.wrong_identity)

    def test_version_mismatch_fails_closed(self):
        self.assert_refused(self.dep_for_archive(self.wrong_version), "resolves as version 9.9.9",
                            archive=self.wrong_version)

    def test_missing_or_malformed_installed_binary_pin_fails_closed(self):
        for check in (None, {}, [], "invalid", {"path": BINARY_PATH, "sha256": "bad"}):
            with self.subTest(check=check):
                dep = copy.deepcopy(self.dep)
                if check is None:
                    del dep["installed_binary_check"]
                else:
                    dep["installed_binary_check"] = check
                self.assert_refused(dep, "no verified installed binary pin")

    def test_binary_outside_package_fails_closed(self):
        dep = copy.deepcopy(self.dep)
        dep["installed_binary_check"]["path"] = "../../bin/widget.js"
        self.assert_refused(dep, "outside its verified package")

    def test_nonexecutable_binary_fails_closed(self):
        self.assert_refused(self.dep_for_archive(self.nonexecutable), "installed binary", archive=self.nonexecutable)

    def test_rebuild_cannot_change_verified_binary_before_linking(self):
        self.assert_refused(self.dep, "platform dependency tree changed after npm rebuild", variant="corrupt-rebuild")

    def test_rebuild_cannot_change_auxiliary_executable_before_linking(self):
        self.assert_refused(self.dep, "platform dependency tree changed after npm rebuild", variant="corrupt-auxiliary")

    def test_rebuild_cannot_add_a_package_before_linking(self):
        self.assert_refused(self.dep, "unexpected package", variant="rebuild-extra-package")

    def test_rebuild_cannot_change_auxiliary_executable_mode_before_linking(self):
        self.assert_refused(self.dep, "platform dependency tree changed after npm rebuild", variant="corrupt-mode")

    def test_ignore_scripts_keeps_binary_verification_and_skips_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, eco = self.run_install(Path(tmp), variant="corrupt-rebuild", ignore_scripts="true")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            executed = subprocess.run([str(eco / "bin/widget")], capture_output=True, text=True, timeout=10)
            self.assertEqual((executed.returncode, executed.stdout), (0, "VERIFIED_PLATFORM_BINARY\n"))

    def test_failed_swap_restores_migrated_install_and_removes_unpublished_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, eco = self.run_install(root, previous=True, failed_swap=True)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Failed to flip", result.stderr)
            self.assert_failed_state(root, eco, previous=True)
            migrations = [line for line in (root / "mv.log").read_text().splitlines() if ".migrating." in line]
            self.assertEqual(len(migrations), 2, migrations)
            self.assertTrue(all(line.startswith("-T -- ") for line in migrations), migrations)

    def test_successful_swap_reports_leftover_for_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, eco = self.run_install(root, previous=True, prune_failure=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assert_verified_launcher(eco)
            self.assertIn("remove it with: rm -rf --", result.stderr)
            self.assertNotIn("restore", result.stderr.lower())
            migrations = [line for line in (root / "mv.log").read_text().splitlines() if ".migrating." in line]
            self.assertEqual(len(migrations), 1, migrations)

    def test_versioned_prefix_is_created_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, eco = self.run_install(root, collision=True)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("File exists", result.stderr)
            survivors = list((eco / "tools").glob("widget-1.0.0-fixed-*/sentinel"))
            self.assertEqual(len(survivors), 1)
            self.assertEqual(survivors[0].read_text(), "collision survives\n")
            self.assertFalse((eco / "bin/widget").exists())

    def test_pruning_never_deletes_newly_published_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, eco = self.run_install(Path(tmp), previous_is_new=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assert_verified_launcher(eco)

    def dep_for_archive(self, archive):
        dep = copy.deepcopy(self.dep)
        payload = archive.read_bytes()
        dep["sha256"] = hashlib.sha256(payload).hexdigest()
        dep["integrity"] = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode()
        return dep

    def assert_verified_launcher(self, eco):
        executed = subprocess.run([str(eco / "bin/widget")], capture_output=True, text=True, timeout=10)
        self.assertEqual((executed.returncode, executed.stdout), (0, "VERIFIED_PLATFORM_BINARY\n"))

    def assert_failed_state(self, root, eco, *, previous=False):
        self.assertFalse((eco / "bin/widget").exists(), "failed install must not publish its launcher")
        if previous:
            self.assertEqual((eco / "tools/widget-1.0.0/prior").read_text(), "keep prior install\n")
        self.assertEqual(list((eco / "tools").glob("widget-1.0.0-*")), [], "unpublished prefixes must be removed")
        if (root / "outside/sentinel").exists():
            self.assertEqual((root / "outside/sentinel").read_text(), "must survive\n")

    def assert_refused(self, dep, message, **options):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before_npm = options.pop("before_npm", False)
            result, eco = self.run_install(root, dep=dep, **options)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(message, result.stderr)
            self.assert_failed_state(root, eco, previous=options.get("previous", False))
            migrations = [line for line in (root / "mv.log").read_text().splitlines() if ".migrating." in line]
            self.assertEqual(migrations, [], "verification failure must never migrate an old install")
            if before_npm:
                self.assertFalse((root / "npm.log").exists(), "platform verification must precede npm")


@unittest.skipUnless(os.geteuid() != 0, "bootstrap requires a normal user")
class LinuxPrerequisiteTests(unittest.TestCase):
    def test_missing_python3_names_the_prerequisite_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shim = root / "shim"
            shim.mkdir()
            for name in ("uname", "dirname", "mkdir", "curl", "git", "tar", "sha256sum", "realpath", "flock", "jq", "mktemp"):
                (shim / name).symlink_to(shutil.which(name))
            # The negative control against the old bootstrap must stay offline
            # even when its missing-interpreter guard allows installation.
            (shim / "curl").unlink()
            (shim / "curl").write_text('#!/bin/sh\nprintf "fixture refuses network\\n" >&2\nexit 88\n')
            (shim / "curl").chmod(0o755)
            result = subprocess.run([shutil.which("bash"), str(SCRIPT_PATH), "--profile", "foundation-cpu",
                                     "--skip-system-packages"], capture_output=True, text=True, timeout=10,
                                    env={"PATH": str(shim), "HOME": str(root), "ECO_INSTALL_ROOT": str(root / "eco")})
            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            self.assertIn("Missing prerequisites: python3", result.stderr)
            self.assertNotIn("integrity mismatch", result.stderr)
            self.assertFalse((root / "eco").exists())


def pack_existing(directory, env):
    result = subprocess.run(
        [NPM, "pack", "--offline", "--ignore-scripts", "--silent", "--pack-destination", str(directory)],
        cwd=directory, env=env, capture_output=True, text=True, timeout=60, check=True,
    )
    return directory / result.stdout.strip().splitlines()[-1]
