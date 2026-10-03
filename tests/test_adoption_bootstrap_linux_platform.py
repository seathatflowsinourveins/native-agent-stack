"""Offline Linux integration checks ported from the macOS platform-dependency tests.

Real npm installs local fixture tarballs. Only curl is replaced, so the shipped
fetch/checksum, Node resolution, rebuild and publication paths actually run.
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
BINARY_PATH = "vendor/x86_64-unknown-linux-musl/bin/codex"
VERIFIED_BINARY = b"#!/bin/sh\nprintf 'VERIFIED_PLATFORM_BINARY\\n'\n"


class LinuxPlatformPinTests(unittest.TestCase):
    def test_codex_pins_the_registry_alias_archive_and_native_binary(self):
        pin = next(tool for tool in load_pins()["tools"] if tool["id"] == "codex")
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
        }
        (root / "empty-npmrc").touch()
        (root / "empty-global-npmrc").touch()

        def pack(name, manifest, binary):
            directory = root / name
            directory.mkdir()
            (directory / "package.json").write_text(json.dumps(manifest))
            native = directory / BINARY_PATH
            native.parent.mkdir(parents=True)
            native.write_bytes(binary)
            native.chmod(0o755)
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
        cls.no_binary = pack("no-binary", manifest, VERIFIED_BINARY)
        # A fixture lacking the native executable, packed by npm itself.
        (root / "no-binary" / BINARY_PATH).unlink()
        cls.no_binary = pack_existing(root / "no-binary", cls.npm_env)

        cls.wrappers = {}
        for variant in ("runtime", "missing-dependency", "corrupt-rebuild"):
            directory = root / variant
            (directory / "bin").mkdir(parents=True)
            (directory / "bin" / "widget.js").write_text(
                '#!/usr/bin/env node\n'
                'const path = require("path");\n'
                'const root = path.dirname(require.resolve("fixture-linux-x64/package.json"));\n'
                f'const result = require("child_process").spawnSync(path.join(root, "{BINARY_PATH}"), '
                'process.argv.slice(2), {stdio: "inherit"});\n'
                'process.exit(result.status === null ? 1 : result.status);\n'
            )
            (directory / "bin" / "widget.js").chmod(0o755)
            wrapper = {"name": "fixture-wrapper", "version": "1.0.0",
                       "bin": {"widget": "bin/widget.js"}}
            if variant != "missing-dependency":
                wrapper["optionalDependencies"] = {"fixture-linux-x64": f"file:{cls.unverified}"}
            if variant == "corrupt-rebuild":
                (directory / "corrupt.js").write_text(
                    'const fs = require("fs"), path = require("path");\n'
                    'const root = path.dirname(require.resolve("fixture-linux-x64/package.json"));\n'
                    f'fs.writeFileSync(path.join(root, "{BINARY_PATH}"), "CORRUPTED\\n");\n'
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
                    ignore_scripts="false"):
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
        source = SCRIPT_PATH.read_text()
        names = ("verify_sha256", "fetch", "canonical_path", "prune_old_version",
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
            + "trap cleanup EXIT\ntrap 'exit 130' INT\ntrap 'exit 143' TERM\ntrap 'exit 129' HUP\n"
            + f"install_npm widget 1.0.0 {shlex.quote(wrapper_url)} {pin['sha256']} {ignore_scripts}\n"
        )
        env = {**self.npm_env, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}
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
                            "integrity mismatch")

    def test_missing_integrity_fails_closed(self):
        dep = copy.deepcopy(self.dep)
        del dep["integrity"]
        self.assert_refused(dep, "integrity")

    def test_missing_dependency_metadata_fails_closed(self):
        dep = copy.deepcopy(self.dep)
        del dep["sha256"]
        self.assert_refused(dep, "no verified sha256")

    def test_missing_dependency_from_npm_is_installed_as_verified_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, eco = self.run_install(Path(tmp), variant="missing-dependency")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            binary = eco / "tools/widget-1.0.0/lib/node_modules/fixture-linux-x64" / BINARY_PATH
            self.assertEqual(binary.read_bytes(), VERIFIED_BINARY)

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

    def test_rebuild_cannot_change_verified_binary_before_linking(self):
        self.assert_refused(self.dep, "installed binary", variant="corrupt-rebuild")

    def test_ignore_scripts_keeps_binary_verification_and_skips_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, eco = self.run_install(Path(tmp), variant="corrupt-rebuild", ignore_scripts="true")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            executed = subprocess.run([str(eco / "bin/widget")], capture_output=True, text=True, timeout=10)
            self.assertEqual((executed.returncode, executed.stdout), (0, "VERIFIED_PLATFORM_BINARY\n"))

    def assert_refused(self, dep, message, **options):
        with tempfile.TemporaryDirectory() as tmp:
            result, eco = self.run_install(Path(tmp), dep=dep, **options)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(message, result.stderr)
            self.assertFalse((eco / "bin/widget").exists(), "failed install must not publish its launcher")
            if options.get("previous"):
                self.assertEqual((eco / "tools/widget-1.0.0/prior").read_text(), "keep prior install\n")


def pack_existing(directory, env):
    result = subprocess.run(
        [NPM, "pack", "--offline", "--ignore-scripts", "--silent", "--pack-destination", str(directory)],
        cwd=directory, env=env, capture_output=True, text=True, timeout=60, check=True,
    )
    return directory / result.stdout.strip().splitlines()[-1]
