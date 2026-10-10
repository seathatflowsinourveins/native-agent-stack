"""J-744 source parity and synthetic filesystem controls, never native adoption.

The original install/identity strings are read from the plan. Tests rebound only
their HOME path reference to a named fixture root; no host profile is read. A
small artifact stand-in supplies the declared size/digest outcomes so custody
branches can run without the private 131-MiB package. Other SHA256 checks and
the installed package JSON/BUILD_SHA checks use the real native tools. No npm,
systemd, gateway, provider or native client is invoked by these controls.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"
PREFIX_NAME = "omniroute-3.8.51-5f4b3d577-affinity-pr15167"
DECISION_PIN = "0fb32ee583589f1a0809b20d18dff40ce2f65a1c"
WRAPPER_SHA = "672063a12174d46f7065ae7bb9adf1ed268c958cd264f64a25d0af3f74ae45bc"
SHIM_SHA = "b6ae900224df3dc73fff2a50b3d7206d78895c6147e93e80b62e66d423e69854"
ASSETS = (
    "gpt-gateway-topology.json", "gpt-gateway-client-accept.sh", "omniroute.service",
    "omniroute-serve.sh", "omniroute-lsof-shim-v2.sh",
    "omniroute.service.d/10-show-log.conf", "omniroute.env.example",
)


def gateway_row():
    data = json.loads((PLAN / "install-plan.json").read_text())
    return next(row for row in data["owners"] if row["slot"] == "gpt-gateway")


def checker_module():
    spec = importlib.util.spec_from_file_location("j744_check_plan", PLAN / "check_plan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GatewayCompositionSources(unittest.TestCase):
    def test_supplied_package_and_exact_assets_have_distinct_identity(self):
        row = gateway_row()
        identity = row["prebuilt_composition"]
        self.assertEqual(identity["decision_pin"], DECISION_PIN)
        self.assertEqual(identity["build_sha"], "5f4b3d577")
        self.assertEqual(identity["pr15167_pin"], "0585aba5589d5a1f49243a13a8db249558e7c9e3")
        self.assertEqual(row["package_integrity"]["bytes"], 137823643)
        self.assertEqual(row["package_integrity"]["sha256"],
                         "d3fda90c297ed1ecbaa82ca42298735ce0b393db9a07bad0b4b79efce118ebe2")
        self.assertFalse(row["source_build"])
        self.assertFalse(identity["carries_pr13788"])
        self.assertIsNone(identity["public_download_url"])
        for name, size, digest in (("omniroute-serve.sh", 1289, WRAPPER_SHA),
                                   ("omniroute-lsof-shim-v2.sh", 1369, SHIM_SHA)):
            with self.subTest(asset=name):
                content = (PLAN / "config" / name).read_bytes()
                self.assertEqual((len(content), hashlib.sha256(content).hexdigest()), (size, digest))
        self.assertEqual((PLAN / "config/omniroute-lsof-shim-v2.sh").read_bytes(),
                         (ROOT / "evidence/artifacts/omniroute-sol-max-20260930/scripts/lsof-shim-v2.sh.txt").read_bytes())

    def test_declared_commands_and_all_three_stages_match_the_native_dispatchers(self):
        checker = checker_module()
        row = gateway_row()
        install = checker.functions((PLAN / "install.sh").read_text())
        accept = checker.functions((PLAN / "accept.sh").read_text())
        self.assertEqual(checker.run_commands("gpt-gateway", install, set()), row["commands"])
        self.assertEqual(checker.checks_of(accept["gpt-gateway"]),
                         [(stage, "gpt-gateway", entry["kind"], entry["command"])
                          for stage, entry in row["acceptance"].items()])
        body = install["gpt-gateway"]
        self.assertLess(body.index("run_command "), body.index("copy_config "))
        commands = "\n".join(row["commands"])
        self.assertIn('npm install -g --prefix "$gateway_prefix" --no-audit --no-fund "$gateway_tarball"', commands)
        for forbidden in ("npm view", "npm ci", "build:release", "git clone", "systemctl --user restart",
                          "systemctl --user start", "omniroute-canary-check.py"):
            self.assertNotIn(forbidden, commands)
        for entry in row["acceptance"].values():
            self.assertNotIn("omniroute-canary-check.py", entry["command"])

    def test_wrapper_unit_drop_in_and_explicit_route_agree_with_the_map(self):
        topology = json.loads((PLAN / "config/gpt-gateway-topology.json").read_text())
        route = topology["pool_fallback"]
        self.assertEqual((route["model"], route["model_reasoning_effort"], route["base_url"]),
                         ("cx/gpt-6.1-sol-max", "max", "http://127.0.0.1:21128/v1"))
        entries = json.loads((ROOT / "adoption/new-wsl/client-config-map.json").read_text())["entries"]
        overrides = {key: entry["override"] for entry in entries if "override" in entry
                     for key in entry["match"] if key.startswith("codex/omniroute/")}
        for setting in ("model", "model_reasoning_effort"):
            self.assertEqual(overrides["codex/omniroute/" + setting], route[setting])
        self.assertEqual(overrides["codex/omniroute/web_search"], "disabled")
        self.assertFalse(overrides["codex/omniroute/features.standalone_web_search"])
        self.assertFalse(overrides["codex/omniroute/model_providers.omniroute.supports_standalone_web_search"])
        script = (PLAN / "config/gpt-gateway-client-accept.sh").read_text()
        invocation = script.split("OMNIROUTE_API_KEY=keyless-loopback ", 1)[1].split("--ephemeral", 1)[0]
        argv = shlex.split(invocation.replace("\\\n", " "))
        self.assertEqual(argv[argv.index("-m") + 1], route["model"])
        config = dict(argv[i + 1].split("=", 1) for i, arg in enumerate(argv) if arg == "-c")
        self.assertEqual(config["model_reasoning_effort"], route["model_reasoning_effort"])
        self.assertEqual(config["model_provider"], route["model_provider"])
        self.assertEqual(json.loads(config["model_providers.omniroute.base_url"]), route["base_url"])
        self.assertEqual(config["web_search"], "disabled")
        unit = (PLAN / "config/omniroute.service").read_text()
        self.assertIn("ExecStart=%h/.local/share/omniroute-builds/" + PREFIX_NAME + "/omniroute-serve.sh\n", unit)
        self.assertEqual((PLAN / "config/omniroute.service.d/10-show-log.conf").read_text(),
                         "[Service]\nEnvironment=OMNIROUTE_SHOW_LOG=1\n")

    def test_supersession_adds_a_note_without_changing_any_historical_verdict_field(self):
        data = json.loads((ROOT / "evidence/artifacts/final-architecture-round2-20261004/verdicts.json").read_text())
        row = dict(next(row for row in data["verdicts"] if row["gap_slot"] == "gpt-gateway-topology"))
        note = row.pop("supersession_note")
        self.assertEqual(note["date_utc"], "2026-10-05")
        self.assertIn(DECISION_PIN, note["source"])
        digest = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        # Original gateway object at the worker's reviewed 44ac761 baseline.
        self.assertEqual(digest, "d17c50d00da297d6a421d1482c4f2f230ddbaf2d902aecb95b9520b13417fc6f")

    def test_fresh_client_requires_the_loaded_active_wrapper_and_drop_in(self):
        command = gateway_row()["acceptance"]["after_sign_in"]["command"]
        client = command.index('bash "$config_root/gpt-gateway-client-accept.sh"')
        for binding in ("systemctl --user is-active --quiet omniroute.service",
                        "systemctl --user show -p ExecStart --value omniroute.service",
                        "systemctl --user show -p DropInPaths --value omniroute.service",
                        "systemctl --user show --timestamp=us+utc -p ActiveEnterTimestamp omniroute.service"):
            self.assertLess(command.index(binding), client)

    @unittest.skipIf(sys.platform == "darwin",
                     "WSL systemd timestamp integration requires GNU date parsing and GNU stat nanosecond formats")
    def test_active_process_must_have_started_after_both_unit_files(self):
        """Real date/stat comparison, synthetic systemd timestamps; no manager call."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            units = root / ".config/systemd/user"
            units.mkdir(parents=True)
            unit = units / "omniroute.service"
            drop_in = units / "omniroute.service.d/10-show-log.conf"
            drop_in.parent.mkdir()
            unit.write_text("fixture unit\n")
            drop_in.write_text("fixture drop-in\n")
            binary = root / "bin"
            binary.mkdir()
            manager = binary / "systemctl"
            manager.write_text('#!/bin/sh\n[ "$*" = "--user show --timestamp=us+utc -p ActiveEnterTimestamp omniroute.service" ] || exit 99\nprintf "ActiveEnterTimestamp=%s\\n" "$FIXTURE_STARTED"\n')
            manager.chmod(0o755)
            for stage in ("service_health", "after_sign_in"):
                command = gateway_row()["acceptance"][stage]["command"]
                start = command.index('gateway_started="')
                end = command.index("\ndone", start) + len("\ndone")
                freshness = command[start:end]
                for case, started, unit_ns, drop_in_ns in (
                    ("fresh", "2026-10-06 23:00:03.000001 UTC", 1791327601000000000, 1791327602000000000),
                    ("old-unit", "2026-10-06 23:00:03 UTC", 1791327604000000000, 1791327602000000000),
                    ("old-drop-in", "2026-10-06 23:00:03 UTC", 1791327601000000000, 1791327604000000000),
                    ("same-microsecond", "2026-10-06 23:00:03.000001 UTC", 1791327601000000000, 1791327603000001000),
                    ("missing-start", "", 1791327601000000000, 1791327602000000000),
                    ("malformed-start", "not a timestamp", 1791327601000000000, 1791327602000000000),
                ):
                    with self.subTest(stage=stage, case=case):
                        os.utime(unit, ns=(unit_ns, unit_ns))
                        os.utime(drop_in, ns=(drop_in_ns, drop_in_ns))
                        result = subprocess.run(["bash", "-euo", "pipefail", "-c", freshness],
                                                env={"PATH": str(binary) + os.pathsep + os.environ["PATH"],
                                                     "HOME": str(root), "FIXTURE_STARTED": started},
                                                capture_output=True, text=True, timeout=10)
                        if case == "fresh":
                            self.assertEqual(result.returncode, 0, result.stderr)
                        else:
                            self.assertNotEqual(result.returncode, 0, result.stderr)


@unittest.skipIf(sys.platform == "darwin",
                 "WSL gateway composition executes GNU sha256sum --check --status, stat -c and readlink path guards")
class GatewayCompositionFilesystemControls(unittest.TestCase):
    """Execute the selected glue with isolated files and a declared artifact stand-in."""

    @classmethod
    def setUpClass(cls):
        for tool in ("bash", "node", "sha256sum", "stat", "readlink", "cmp"):
            if shutil.which(tool) is None:
                raise unittest.SkipTest(f"{tool} is required for the synthetic controls")
        cls.row = gateway_row()
        cls.identity = cls.row["acceptance"]["post_install"]["command"].split("\nDATA_DIR=", 1)[0]

    def setUp(self):
        cache = Path(os.environ.get("NATIVE_STACK_TEST_TMPDIR", Path.home() / ".cache/native-agent-stack/j744-tests"))
        cache.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="gateway-", dir=cache)
        self.addCleanup(self.temporary.cleanup)
        self.scratch = Path(self.temporary.name)
        self.fixture_home = self.scratch / "fixture-home"
        self.plan = self.scratch / "plan"
        self.config = self.scratch / "config"
        self.tools = self.scratch / "tools"
        self.prefix = self.fixture_home / ".local/share/omniroute-builds" / PREFIX_NAME
        self.package = self.prefix / "lib/node_modules/omniroute"
        self.alias = self.fixture_home / ".local/bin/omniroute"
        self.unit = self.fixture_home / ".config/systemd/user/omniroute.service"
        self.drop_in = self.unit.parent / "omniroute.service.d/10-show-log.conf"
        for name in ASSETS:
            for directory in (self.plan / "config", self.config):
                target = directory / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(PLAN / "config" / name, target)
        for relative, content in (("package.json", '{"version":"3.8.51"}\n'),
                                  ("dist/BUILD_SHA", "5f4b3d577\n"),
                                  ("bin/omniroute.mjs", "#!/bin/sh\nexit 99\n")):
            target = self.package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        (self.package / "bin/omniroute.mjs").chmod(0o755)
        (self.prefix / "bin").mkdir()
        (self.prefix / "bin/omniroute").symlink_to("../lib/node_modules/omniroute/bin/omniroute.mjs")
        self.alias.parent.mkdir(parents=True)
        self.alias.symlink_to(self.prefix / "bin/omniroute")
        for source, target in (("omniroute-serve.sh", self.prefix / "omniroute-serve.sh"),
                               ("omniroute-lsof-shim-v2.sh", self.prefix / "shim/lsof"),
                               ("omniroute.service", self.unit),
                               ("omniroute.service.d/10-show-log.conf", self.drop_in)):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PLAN / "config" / source, target)
            if target.is_relative_to(self.prefix):
                target.chmod(0o755)
        self.tarball = self.scratch / "synthetic-package.tgz"
        self.tarball.write_bytes(b"synthetic composition fixture; not a native package\n")
        stub = self.scratch / "artifact-stand-ins"
        stub.mkdir()
        for tool in ("stat", "sha256sum"):
            program = stub / tool
            program.write_text(f"#!{sys.executable}\n" +
                               "import hashlib, os, pathlib, subprocess, sys\n" +
                               "tool=pathlib.Path(sys.argv[0]).name\n" +
                               "artifact=os.environ['J744_FIXTURE_ARTIFACT']\n" +
                               "if tool == 'stat' and sys.argv[-1] == artifact:\n" +
                               "    print(os.environ['J744_FIXTURE_BYTES']); sys.exit(0)\n" +
                               "if tool == 'sha256sum':\n" +
                               "    data=sys.stdin.buffer.read()\n" +
                               "    if data.decode().strip().endswith('  '+artifact):\n" +
                               "        digest=hashlib.sha256(pathlib.Path(artifact).read_bytes()).hexdigest()\n" +
                               "        sys.exit(0 if digest == os.environ['J744_FIXTURE_DIGEST'] else 1)\n" +
                               "    sys.exit(subprocess.run([os.environ['J744_NATIVE_SHA'], *sys.argv[1:]], input=data).returncode)\n" +
                               "sys.exit(subprocess.run([os.environ['J744_NATIVE_STAT'], *sys.argv[1:]]).returncode)\n")
            program.chmod(0o755)
        self.env = {
            "PATH": str(stub) + os.pathsep + os.environ["PATH"],
            "plan_dir": str(self.plan), "config_root": str(self.config), "tool_root": str(self.tools),
            "gateway_fixture_home": str(self.fixture_home),
            "OMNIROUTE_COMPOSITION_TARBALL": str(self.tarball),
            "J744_FIXTURE_ARTIFACT": str(self.tarball), "J744_FIXTURE_BYTES": "137823643",
            "J744_FIXTURE_DIGEST": hashlib.sha256(self.tarball.read_bytes()).hexdigest(),
            "J744_NATIVE_SHA": shutil.which("sha256sum"), "J744_NATIVE_STAT": shutil.which("stat"),
        }

    def run_recipe(self, program):
        # Rebound only the path root, keeping the frozen glue and guards intact.
        return subprocess.run(["bash", "-euo", "pipefail", "-c", program.replace("$HOME", "$gateway_fixture_home")],
                              env=self.env, capture_output=True, text=True, timeout=15)

    def test_all_three_stages_require_the_same_prebuilt_identity(self):
        for stage, entry in self.row["acceptance"].items():
            with self.subTest(stage=stage):
                self.assertTrue(entry["command"].startswith(self.identity + "\n"))
        result = self.run_recipe(self.identity)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_identity_rejects_each_missing_or_different_property(self):
        targets = (self.package / "package.json", self.package / "dist/BUILD_SHA",
                   self.prefix / "omniroute-serve.sh", self.prefix / "shim/lsof", self.unit,
                   self.drop_in, self.config / "gpt-gateway-topology.json",
                   self.config / "gpt-gateway-client-accept.sh")
        for target in targets:
            original = target.read_bytes()
            for kind in ("different", "missing"):
                with self.subTest(asset=str(target.relative_to(self.scratch)), kind=kind):
                    if kind == "different":
                        target.write_bytes(b"foreign fixture\n")
                    else:
                        target.unlink()
                    result = self.run_recipe(self.identity)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    target.write_bytes(original)
                    if target.is_relative_to(self.prefix):
                        target.chmod(0o755)

    def test_preflight_passes_the_recognized_composition_without_mutating_files(self):
        before = {path: path.read_bytes() for path in (self.unit, self.drop_in, self.prefix / "omniroute-serve.sh")}
        result = self.run_recipe(self.row["commands"][0])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_preflight_refuses_a_foreign_regular_alias_and_keeps_its_bytes(self):
        self.alias.unlink()
        content = b"foreign owner alias\n"
        self.alias.write_bytes(content)
        result = self.run_recipe(self.row["commands"][0])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needs_owner", result.stderr)
        self.assertEqual(self.alias.read_bytes(), content)

    def test_preflight_refuses_a_foreign_symlink_alias_without_repointing_it(self):
        self.alias.unlink()
        foreign = self.scratch / "foreign-executable"
        foreign.write_text("foreign owner\n")
        self.alias.symlink_to(foreign)
        result = self.run_recipe(self.row["commands"][0])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needs_owner", result.stderr)
        self.assertEqual(self.alias.readlink(), foreign)

    def test_recipe_migrates_a_recognized_old_plan_alias_to_the_supplied_prefix(self):
        previous = self.tools / "omniroute-3.8.51/lib/node_modules/omniroute/bin/omniroute.mjs"
        previous.parent.mkdir(parents=True)
        previous.write_text("old plan fixture, never executed\n")
        self.alias.unlink()
        self.alias.symlink_to(previous)
        for command in self.row["commands"][:2]:
            result = self.run_recipe(command)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.alias.resolve(), self.package / "bin/omniroute.mjs")
        self.assertEqual(previous.read_text(), "old plan fixture, never executed\n")
        self.assertEqual(hashlib.sha256((self.prefix / "omniroute-serve.sh").read_bytes()).hexdigest(), WRAPPER_SHA)
        self.assertEqual(hashlib.sha256((self.prefix / "shim/lsof").read_bytes()).hexdigest(), SHIM_SHA)

    def test_preflight_refuses_a_changed_source_asset_before_installed_assets_are_touched(self):
        installed = (self.prefix / "omniroute-serve.sh").read_bytes()
        (self.plan / "config/omniroute-serve.sh").write_text("changed source fixture\n")
        result = self.run_recipe(self.row["commands"][0])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needs_owner", result.stderr)
        self.assertEqual((self.prefix / "omniroute-serve.sh").read_bytes(), installed)

    def test_preflight_refuses_an_asset_symlink_even_when_its_bytes_match(self):
        foreign = self.scratch / "foreign-unit"
        shutil.copyfile(self.unit, foreign)
        self.unit.unlink()
        self.unit.symlink_to(foreign)
        result = self.run_recipe(self.row["commands"][0])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needs_owner", result.stderr)
        self.assertEqual(self.unit.readlink(), foreign)

    def test_preflight_refuses_foreign_assets_and_keeps_them(self):
        for target in (self.unit, self.drop_in, self.prefix / "omniroute-serve.sh", self.prefix / "shim/lsof",
                       self.config / "gpt-gateway-topology.json", self.package / "dist/BUILD_SHA"):
            original = target.read_bytes()
            with self.subTest(asset=str(target.relative_to(self.scratch))):
                target.write_bytes(b"foreign owner bytes\n")
                result = self.run_recipe(self.row["commands"][0])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("needs_owner", result.stderr)
                self.assertEqual(target.read_bytes(), b"foreign owner bytes\n")
                target.write_bytes(original)

    def test_preflight_refuses_a_different_artifact_digest_or_size(self):
        for key, value in (("J744_FIXTURE_BYTES", "1"), ("J744_FIXTURE_DIGEST", "0" * 64)):
            original = self.env[key]
            with self.subTest(property=key):
                self.env[key] = value
                result = self.run_recipe(self.row["commands"][0])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("needs_owner", result.stderr)
                self.env[key] = original

    def test_identity_refuses_symlinks_for_each_regular_package_and_executable_asset(self):
        for target in (self.package / "package.json", self.package / "dist/BUILD_SHA",
                       self.prefix / "omniroute-serve.sh", self.prefix / "shim/lsof"):
            with self.subTest(asset=str(target.relative_to(self.scratch))):
                content = target.read_bytes()
                mode = target.stat().st_mode & 0o777
                foreign = self.scratch / ("foreign-" + target.name)
                foreign.write_bytes(content)
                foreign.chmod(mode)
                target.unlink()
                target.symlink_to(foreign)
                result = self.run_recipe(self.identity)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                target.unlink()
                target.write_bytes(content)
                target.chmod(mode)

    def test_exact_previous_plan_assets_migrate_but_unknown_bytes_remain_guarded(self):
        expected = {
            "gpt-gateway-client-accept.sh": "d317011252d368578ad1da4008c6d80118c4c95c0f641d2ba18342f45b3eecc2",
            "gpt-gateway-topology.json": "fb4664f629e15351454ed448963bcd1057d934c1657a3c317bfe508d6cabcc0e",
            "omniroute.service": "d5d71850d72c8e85c01df82a3fc4265d452e891333d197ced14c0ca26df6b074",
        }
        previous = {}
        for name, digest in expected.items():
            path = "evidence/artifacts/new-wsl-install-plan-20261002/config/" + name
            source = subprocess.run(["git", "show", "44ac761:" + path], cwd=ROOT,
                                    capture_output=True, timeout=10)
            if source.returncode:
                self.skipTest("reviewed 44ac761 historical blobs are absent in this shallow checkout")
            self.assertEqual(hashlib.sha256(source.stdout).hexdigest(), digest)
            previous[name] = source.stdout
        for name, content in previous.items():
            (self.config / name).write_bytes(content)
        self.unit.write_bytes(previous["omniroute.service"])
        result = self.run_recipe(self.row["commands"][0])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        body = checker_module().functions((PLAN / "install.sh").read_text())["copy_config"]
        for name in previous:
            result = self.run_recipe("copy_config() {\n" + body + "\n}\ncopy_config " + shlex.quote(name))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((self.config / name).read_bytes(), (self.plan / "config" / name).read_bytes())
        systemctl = self.scratch / "artifact-stand-ins/systemctl"
        systemctl.write_text('#!/bin/sh\n[ "$*" = "--user daemon-reload" ] || exit 97\n')
        systemctl.chmod(0o755)
        result = self.run_recipe(self.row["commands"][2])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.unit.read_bytes(), (self.plan / "config/omniroute.service").read_bytes())
        # Existing foreign-byte and equal-byte symlink controls remain separate negatives.


if __name__ == "__main__":
    unittest.main()
