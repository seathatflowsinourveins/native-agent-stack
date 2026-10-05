"""Local integration controls for the read-only, stdin-portable PR-0 probe."""

import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tools/adoption/host_baseline_probe.py"
NATIVE_FIXTURE = r'''
from pathlib import Path
import sys
name = Path(sys.argv[0]).name
if name in {"sudo", "sudo-rs"}:
    (Path(sys.argv[0]).parent / "privilege-launcher-invoked").touch()
    sys.exit(99)
elif name == "date":
    print("2026-10-04T23:59:00Z")
elif name == "dpkg-query":
    package = sys.argv[-1]
    if package in {"rust-coreutils", "rust-findutils", "sudo-rs"}:
        print("dpkg-query: no packages found matching " + package, file=sys.stderr)
        sys.exit(1)
    print(package + " 1.2.3")
elif name == "stat":
    print("440 fixture-owner 42")
elif name == "getent":
    print("fixture-owner:x:1000:1000::/private-fixture-home:/bin/bash")
elif name == "id":
    print("fixture-owner")
elif name == "readlink" and "--version" not in sys.argv:
    print("/usr/bin/sudo")
elif name == "bwrap":
    print("this output must be discarded", file=sys.stderr)
    sys.exit(1)
elif name == "git":
    print("1" * 40)
elif name == "cat":
    print("1")
elif name == "env" and (Path(sys.argv[0]).parent / "planted-output").exists():
    print((Path(sys.argv[0]).parent / "planted-output").read_text())
else:
    print(name + " (fixture native) 1.2.3")
'''


def observations(value):
    if isinstance(value, dict):
        if "command" in value:
            yield value
        else:
            for item in value.values():
                yield from observations(item)


class HostBaselineProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        fixture = self.bin / "native-fixture"
        fixture.write_text(f"#!{sys.executable}\n" + NATIVE_FIXTURE)
        fixture.chmod(0o755)
        commands = (
            "date dpkg-query env timeout readlink find xargs stat getent id git cat "
            "sudo sudo-rs bwrap claude codex systemd-run ionice watch script flock "
            "chrt taskset unshare nsenter runuser busybox"
        ).split()
        for name in commands:
            (self.bin / name).symlink_to(fixture)
        self.env = {**os.environ, "HOME": str(self.home), "PATH": str(self.bin) + os.pathsep + os.defpath}
        (self.home / ".codex").mkdir()
        (self.home / ".codex/config.toml").write_text(
            'allow_login_shell = false\n[features]\nshell_snapshot = false\n'
            '[shell_environment_policy]\ninherit = "none"\n'
            '[shell_environment_policy.set]\nPRIVATE_SENTINEL = "must-never-be-rendered"\n'
        )
        (self.home / ".claude").mkdir()
        (self.home / ".claude/settings.json").write_text(json.dumps({
            "env": {"CLAUDE_CODE_SHELL": "must-never-be-rendered", "PRIVATE_SENTINEL": "must-never-be-rendered"},
        }))
        (self.home / "code/native-agent-stack").mkdir(parents=True)

    def run_probe(self, *, stdin=False, optimized=False):
        argv = [sys.executable] + (["-O"] if optimized else []) + (["-"] if stdin else [str(PROBE)])
        return subprocess.run(
            argv, input=PROBE.read_bytes() if stdin else None,
            capture_output=True, env=self.env, timeout=30, check=False,
        )

    def test_shape_and_retained_native_failures(self):
        result = self.run_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        data = json.loads(result.stdout)
        self.assertEqual(set(data), {
            "schema_version", "probe", "host_checkout", "os_release", "architecture",
            "coreutils", "findutils", "sudo", "passwordless_sudo", "launchers",
            "optional_commands", "kernel", "passwd_shell", "clients", "rendered_config",
        })
        self.assertEqual(data["schema_version"], 1)
        records = list(observations(data))
        self.assertGreater(len(records), 40)
        for record in records:
            self.assertEqual(set(record), {"command", "exit", "output", "date_utc"})
            self.assertIsInstance(record["command"], str)
            self.assertIsInstance(record["exit"], int)
            self.assertEqual(set(record["date_utc"]), {"command", "exit", "output"})
            self.assertEqual(record["date_utc"]["exit"], 0)
            self.assertRegex(record["date_utc"]["output"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(data["coreutils"]["packages"]["rust-coreutils"]["exit"], 1)
        self.assertIn("absent", data["coreutils"]["packages"]["rust-coreutils"]["output"])
        self.assertEqual(data["kernel"]["bwrap"]["exit"], 1)
        self.assertEqual(data["kernel"]["bwrap"]["output"], "")
        self.assertEqual(data["host_checkout"]["output"], "1" * 40)
        self.assertEqual(data["passwd_shell"]["output"], "/bin/bash")
        self.assertEqual(data["passwordless_sudo"]["marker"]["output"], {"exists": True, "mode": "440", "size_bytes": 42})
        self.assertNotIn(b"fixture-owner", result.stdout)
        self.assertNotIn(str(self.home).encode(), result.stdout)
        self.assertNotIn(b"must-never-be-rendered", result.stdout)
        self.assertNotIn(b"PRIVATE_SENTINEL", result.stdout)
        for record in data["rendered_config"].values():
            def names_and_booleans(value):
                if isinstance(value, dict):
                    return all(isinstance(k, str) and names_and_booleans(v) for k, v in value.items())
                return isinstance(value, bool)
            self.assertTrue(names_and_booleans(record["output"]))
        self.assertFalse(data["rendered_config"]["codex"]["output"]["allow_login_shell"]["enabled"])
        self.assertTrue(data["rendered_config"]["codex"]["output"]["shell_environment_policy.inherit"]["is_none"])
        self.assertEqual(data["rendered_config"]["claude"]["output"], {"CLAUDE_CODE_SHELL": True})
        self.assertFalse((self.bin / "privilege-launcher-invoked").exists())

    def test_stdin_and_file_checksum_are_actual_probe_bytes(self):
        expected = hashlib.sha256(PROBE.read_bytes()).hexdigest()
        for stdin in (False, True):
            with self.subTest(stdin=stdin):
                result = self.run_probe(stdin=stdin)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["probe"]["output"], expected)

    def test_private_output_exits_three_without_any_output(self):
        planted = ["/" + "home" + "/planted-private-path", pwd.getpwuid(os.getuid()).pw_name.upper()]
        for value in planted:
            for optimized in (False, True):
                with self.subTest(kind="home" if value == planted[0] else "login", optimized=optimized):
                    (self.bin / "planted-output").write_text(value)
                    result = self.run_probe(stdin=True, optimized=optimized)
                    self.assertEqual(result.returncode, 3)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(result.stderr, b"")

    def test_no_field_invokes_sudo_static(self):
        text = PROBE.read_text()
        outer = ast.parse(text)
        source = ast.literal_eval(outer.body[0].value)
        tree = ast.parse(source)
        namespace = {"__name__": "probe_static_test", "__file__": str(PROBE), "SOURCE": source}
        exec(compile(tree, "<probe-static-test>", "exec"), namespace)
        self.assertTrue({"sudo", "sudo-rs"}.isdisjoint(namespace["VERSION_COMMANDS"]))
        for node in ast.walk(tree):
            if isinstance(node, ast.List) and node.elts:
                head = node.elts[0]
                if isinstance(head, ast.Constant) and isinstance(head.value, str):
                    self.assertNotIn(Path(head.value).name, {"sudo", "sudo-rs"})
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and " " in node.value:
                self.assertIsNone(re.search(r"(?:^|[;&|]|\$\()\s*(?:[\w/.-]*/)?sudo(?:-rs)?(?:\s|$)", node.value))


if __name__ == "__main__":
    unittest.main()
