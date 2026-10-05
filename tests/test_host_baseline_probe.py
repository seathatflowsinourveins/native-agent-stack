"""Local integration controls for the read-only, stdin-portable PR-0 probe."""

import ast
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


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
    with_status = any("${db:Status-Status}" in arg for arg in sys.argv)
    if package == "gdb" and (Path(sys.argv[0]).parent / "dpkg-known-uninstalled").exists():
        print(package + ("\t\tnot-installed" if with_status else " "))
    else:
        print(package + ("\t1.2.3\tinstalled" if with_status else " 1.2.3"))
elif name == "stat":
    print("440 fixture-owner 42")
elif name == "getent":
    print("fixture-owner:x:1000:1000::/private-fixture-home:/bin/bash")
elif name == "id":
    print("fixture-owner")
elif name == "readlink" and "--version" not in sys.argv:
    print("/usr/bin/sudo")
elif name == "bwrap" and "--version" not in sys.argv:
    print("this output must be discarded", file=sys.stderr)
    sys.exit(1)
elif name == "git":
    print("1" * 40)
elif name == "cat":
    print("1")
elif name == "env" and (Path(sys.argv[0]).parent / "planted-output").exists():
    print((Path(sys.argv[0]).parent / "planted-output").read_text())
elif name == "codex":
    print("codex-cli 0.159.3")
    print("this stderr must stay outside the version value", file=sys.stderr)
    if (Path(sys.argv[0]).parent / "codex-failure").exists():
        sys.exit(9)
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


def probe_namespace():
    source = ast.literal_eval(ast.parse(PROBE.read_text()).body[0].value)
    namespace = {"__name__": "probe_test", "__file__": str(PROBE), "SOURCE": source}
    exec(compile(source, "<probe-test>", "exec"), namespace)
    return namespace


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
            "chrt taskset unshare nsenter runuser busybox gdb"
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

    def run_probe(self, *, stdin=False, optimized=False, source=None):
        argv = [sys.executable] + (["-O"] if optimized else []) + (["-"] if stdin else [str(PROBE)])
        return subprocess.run(
            argv, input=(PROBE.read_bytes() if source is None else source) if stdin else None,
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
            "launcher_packages", "debuggers",
            "optional_commands", "kernel", "passwd_shell", "clients", "rendered_config",
        })
        self.assertEqual(data["schema_version"], 1)
        records = list(observations(data))
        self.assertGreater(len(records), 40)
        for record in records:
            self.assertTrue({"command", "exit", "output", "date_utc"} <= set(record))
            self.assertTrue(set(record) <= {"command", "exit", "output", "date_utc", "stderr"})
            self.assertIsInstance(record["command"], str)
            self.assertIsInstance(record["exit"], int)
            self.assertEqual(set(record["date_utc"]), {"command", "exit", "output"})
            self.assertEqual(record["date_utc"]["exit"], 0)
            self.assertRegex(record["date_utc"]["output"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(data["coreutils"]["packages"]["rust-coreutils"]["exit"], 1)
        self.assertIn("absent", data["coreutils"]["packages"]["rust-coreutils"]["output"])
        self.assertEqual(data["kernel"]["bwrap"]["exit"], 1)
        self.assertEqual(data["kernel"]["bwrap"]["output"], "")
        self.assertEqual(data["kernel"]["bwrap_version"]["exit"], 0)
        self.assertEqual(data["clients"]["codex"]["version"]["output"], "codex-cli 0.159.3")
        self.assertEqual(data["clients"]["codex"]["version"]["stderr"], "this stderr must stay outside the version value")
        self.assertEqual(set(data["launcher_packages"]), {"time", "util-linux", "procps", "systemd", "gdb"})
        self.assertEqual(data["debuggers"]["gdb"]["version"]["exit"], 0)
        self.assertEqual(data["passwordless_sudo"]["status"], "unknown")
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

    def test_canonical_checksum_is_self_reported_not_stdin_attestation(self):
        expected = hashlib.sha256(PROBE.read_bytes()).hexdigest()
        wrapped = b"# harmless extra outer-wrapper bytes\n" + PROBE.read_bytes()
        self.assertNotEqual(hashlib.sha256(wrapped).hexdigest(), expected)
        for stdin, source in ((False, None), (True, None), (True, wrapped)):
            with self.subTest(stdin=stdin, wrapped=source is not None):
                result = self.run_probe(stdin=stdin, source=source)
                self.assertEqual(result.returncode, 0, result.stderr)
                identity = json.loads(result.stdout)["probe"]["output"]
                self.assertIsInstance(identity, dict)
                self.assertEqual(identity["canonical_source_sha256"], expected)
                self.assertEqual(identity["basis"], "self_reported_canonical_source")
                self.assertIsNone(identity["executed_input_sha256"])
                self.assertFalse(identity["executed_input_verified"])

    def mocked_main(self, login, document, *, home=None):
        namespace = probe_namespace()
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(namespace["pwd"], "getpwuid", return_value=SimpleNamespace(pw_name=login)), \
                patch.object(namespace["Path"], "home", return_value=self.home if home is None else home), \
                patch.dict(namespace, {"collect": lambda home: document}), \
                patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = namespace["main"]()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_prefix_sharing_home_paths_fail_closed_before_normalization(self):
        homes = Path("/") / "home"
        cases = (
            ("alice", homes / "alicebob" / ".local/bin/env"),
            ("alice", homes / "alice-old" / "bin/env"),
            ("al", homes / "alice" / ".local/bin/env"),
            ("alice", Path("/backup") / "home/alice/bin/env"),
        )
        for login, path in cases:
            for location in ("output", "stderr", "command", "key"):
                with self.subTest(login=login, location=location, path_kind=path.name):
                    record = {"command": "command -v env", "exit": 0, "output": ""}
                    if location == "key":
                        record[str(path)] = False
                    else:
                        record[location] = str(path)
                    self.assertEqual(self.mocked_main(login, {"env": record}, home=homes / login), (3, "", ""))
        for suffix in ("", "/bin/env"):
            with self.subTest(control="current home", suffix=suffix):
                home = homes / "alice"
                document = {"env": {"command": "command -v env", "exit": 0,
                                    "output": str(home) + suffix}}
                code, out, err = self.mocked_main("alice", document, home=home)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out)["env"]["output"], "~" + suffix)
                self.assertEqual(err, "")

    def test_common_logins_do_not_reject_fixed_labels_or_command_names(self):
        document = {
            "os_release": {"command": "read /etc/os-release", "exit": 0,
                           "output": {"ID": "ubuntu", "VERSION_ID": "24.04"}},
            "clients": {"codex": {
                "path": {"command": "command -v codex", "exit": 0, "output": "/usr/bin/codex"},
                "version": {"command": "codex --version", "exit": 0, "output": "codex-cli 0.159.3"},
            }},
            "kernel": {"bwrap": {"command": "bwrap --unshare-user --unshare-pid true",
                                 "exit": 0, "output": ""}},
            "versions": {"env": {"command": "env --version", "exit": 0,
                                 "output": "fixture-userland (fixture native) 1.2.3"}},
        }
        for login in ("ubuntu", "codex", "user"):
            with self.subTest(login=login):
                code, out, err = self.mocked_main(login, document)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out), document)
                self.assertEqual(err, "")

    def test_identity_tokens_and_path_components_still_fail_closed(self):
        cases = (
            ("ubuntu", "/srv/UBUNTU/bin/env"),
            ("codex", "/srv/CODEX/bin/codex"),
            ("user", "warning: USER"),
            ("fixture-login", "/srv/FIXTURE-LOGIN/bin/env"),
            ("fixture-login", "fixture-login-helper (fixture native) 1.2.3"),
            ("alice", "-ualice"),
        )
        for login, value in cases:
            with self.subTest(login=login, value=value):
                document = {"env": {"command": "env --version", "exit": 0, "output": value}}
                self.assertEqual(self.mocked_main(login, document), (3, "", ""))

    def test_committed_claude_banners_are_tool_identity(self):
        banners = {"nativestack-2404": "2.1.289 (Claude Code)",
                   "nativestack2604": "2.1.289 (Claude Code)",
                   "stackmeasure2604": "2.1.288 (Claude Code)"}
        for name, banner in banners.items():
            with self.subTest(artifact=name):
                document = json.loads((ROOT / f"evidence/artifacts/host-baseline-20261004/{name}.json").read_text())
                self.assertEqual(document["clients"]["claude"]["version"]["output"], banner)
                code, out, err = self.mocked_main("claude", document)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out), document)
                self.assertEqual(err, "")

    def test_version_vendor_tag_exemption_is_scoped(self):
        document = {
            "os_release": {"command": "read /etc/os-release", "exit": 0,
                           "output": {"ID": "ubuntu", "VERSION_ID": "24.04"}},
            "gdb": {"command": "gdb --version", "exit": 0,
                    "output": "GNU gdb (Ubuntu 15.1-1ubuntu2) 15.1"},
        }
        code, out, err = self.mocked_main("ubuntu", document)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), document)
        self.assertEqual(err, "")
        for login, command, value in (
                ("ubuntu", "gdb --version", "GNU gdb USER=UBUNTU"),
                ("claude", "claude --version", "/srv/CLAUDE/bin/launcher")):
            with self.subTest(login=login):
                document["gdb"] = {"command": command, "exit": 0, "output": value}
                self.assertEqual(self.mocked_main(login, document), (3, "", ""))

    def test_banner_exemptions_never_hide_explicit_account_forms(self):
        banners = {"claude": "2.1.289 (Claude Code)", "codex": "codex-cli 0.159.3",
                   "gdb": "GNU gdb (GDB) 15.1", "env": "env (GNU coreutils) 9.4"}
        for login, banner in banners.items():
            forms = (
                f"USER={login}", f"LOGNAME={login}", f"--user={login}",
                f"-u {login}", f"{login}@host", f"~{login}",
                f"uid=1000({login})", f"{login}:x:1000:1000", f"{login}: local account",
            )
            for value in (login,) + tuple(f"{banner} {form}" for form in forms):
                with self.subTest(login=login, value=value):
                    document = {"version": {"command": f"{login} --version", "exit": 0,
                                             "output": value}}
                    self.assertEqual(self.mocked_main(login, document), (3, "", ""))

    def test_account_annotations_after_leading_version_labels_fail_closed(self):
        banners = {
            "claude": "2.1.289 (Claude Code)", "codex": "codex-cli 0.159.3",
            "gdb": "GNU gdb (GDB) 15.1", "env": "env (GNU coreutils) 9.4",
            "time": "time (GNU Time) UNKNOWN", "script": "script from util-linux 2.39.3",
            "watch": "watch from procps-ng 4.0.4", "find": "find (GNU findutils) 4.9.0",
        }
        for login, banner in banners.items():
            forms = (
                f"gid=1000({login})", f"groups=1000({login})",
                f"groups=1000({login}),27(sudo)", f"euid=1000({login})", f"egid=1000({login})",
                f"--user {login}", f"--group {login}", f"--owner {login}",
                f"-g {login}", f"-G {login}", f"user: {login}",
                f"user = {login}", f"USER= {login}", f"login {login}",
                f"logged in as {login}", f"Built by {login}",
            )
            for form in forms:
                with self.subTest(login=login, form=form):
                    document = {"version": {"command": f"{login} --version", "exit": 0,
                                             "output": f"{banner} {form}"}}
                    self.assertEqual(self.mocked_main(login, document), (3, "", ""))
            with self.subTest(login=login, control="unmodified banner"):
                document = {"version": {"command": f"{login} --version", "exit": 0,
                                         "output": banner}}
                code, out, err = self.mocked_main(login, document)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out), document)
                self.assertEqual(err, "")

    def test_vendor_labels_cannot_erase_account_syntax_or_stderr(self):
        for value in ("gid=1000(ubuntu)", "groups=1000(ubuntu),27(sudo)",
                      "euid=1000(ubuntu)", "GNU gdb 15.1\nwarning (ubuntu) cannot read"):
            with self.subTest(value=value):
                document = {
                    "os_release": {"command": "read /etc/os-release", "exit": 0,
                                   "output": {"ID": "ubuntu", "VERSION_ID": "24.04"}},
                    "gdb": {"command": "gdb --version", "exit": 0, "output": value},
                }
                self.assertEqual(self.mocked_main("ubuntu", document), (3, "", ""))

    def test_vendor_exemption_is_limited_to_first_banner_group(self):
        for value in ("GNU gdb (Ubuntu 15.1) uid=1000(ubuntu)",
                      "GNU gdb (GDB) (Ubuntu 15.1)"):
            with self.subTest(value=value):
                document = {
                    "os_release": {"command": "read /etc/os-release", "exit": 0,
                                   "output": {"ID": "ubuntu", "VERSION_ID": "24.04"}},
                    "gdb": {"command": "gdb --version", "exit": 0, "output": value},
                }
                self.assertEqual(self.mocked_main("ubuntu", document), (3, "", ""))

    def test_profile_paths_fail_closed_anywhere_regardless_of_login(self):
        profiles = (
            "/mnt/c/" + "Users/alice.HOST/AppData/fixture",
            "/mnt/c/" + "uSeRs/someone-else/AppData/fixture",
            "C:" + chr(92) + "Users" + chr(92) + "alice.HOST" + chr(92) + "AppData",
            "/" + "Users/someone-else/fixture",
            "/" + "home/someone-else/fixture",
        )
        for profile in profiles:
            for location in ("output", "stderr", "command", "key"):
                with self.subTest(profile=profile, location=location):
                    record = {"command": "env --version", "exit": 0, "output": ""}
                    if location == "key":
                        record[profile] = False
                    else:
                        record[location] = profile
                    self.assertEqual(self.mocked_main("alice", {"env": record}), (3, "", ""))

    def test_compound_identities_and_attached_options_fail_closed(self):
        cases = (
            ("alice", "/srv/alice-data/bin/env"),
            ("alice", "/var/lib/alice.d/state"),
            ("alice", "alice.HOST"),
            ("alice", "alice_backup"),
            ("alice", "alice123"),
            ("alice", "-nualice"),
            ("alice", "-galice"),
            ("fixture-login", "fixture-login-helper /srv/fixture-login-data/bin/env"),
            ("user", "stat: cannot statx '/etc/sudoers.d/90-wsl-default-user-data': No such file or directory"),
        )
        for login, value in cases:
            for location in ("output", "stderr"):
                with self.subTest(login=login, value=value, location=location):
                    record = {"command": "stat marker", "exit": 1, "output": ""}
                    record[location] = value
                    self.assertEqual(self.mocked_main(login, {"marker": record}), (3, "", ""))
        document = {"marker": {"command": "stat marker", "exit": 1,
                               "output": "stat: cannot statx '/etc/sudoers.d/90-wsl-default-user': No such file or directory"}}
        code, out, err = self.mocked_main("user", document)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), document)
        self.assertEqual(err, "")

    def test_all_committed_captures_accept_common_logins(self):
        for login in ("claude", "codex", "ubuntu", "user", "alice"):
            for name in ("nativestack-2404", "nativestack2604", "stackmeasure2604"):
                with self.subTest(login=login, artifact=name):
                    document = json.loads((ROOT / f"evidence/artifacts/host-baseline-20261004/{name}.json").read_text())
                    code, out, err = self.mocked_main(login, document)
                    self.assertEqual(code, 0)
                    self.assertEqual(json.loads(out), document)
                    self.assertEqual(err, "")

    def test_dpkg_known_uninstalled_state_retains_zero_exit(self):
        (self.bin / "dpkg-known-uninstalled").touch()
        result = self.run_probe(stdin=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        packages = json.loads(result.stdout)["launcher_packages"]
        self.assertEqual(packages["gdb"]["exit"], 0)
        self.assertIn("${db:Status-Status}", packages["gdb"]["command"])
        self.assertEqual(packages["gdb"]["output"].split("\t"), ["gdb", "", "not-installed"])
        self.assertEqual(packages["util-linux"]["output"].split("\t"), ["util-linux", "1.2.3", "installed"])

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

    def test_codex_failure_retains_exit_and_stderr_separately(self):
        (self.bin / "codex-failure").touch()
        result = self.run_probe(stdin=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        version = json.loads(result.stdout)["clients"]["codex"]["version"]
        self.assertEqual(version["exit"], 9)
        self.assertEqual(version["output"], "codex-cli 0.159.3")
        self.assertEqual(version["stderr"], "this stderr must stay outside the version value")

    def test_unexpected_exceptions_are_silent_exit_three(self):
        for exception in ("KeyError", "KeyboardInterrupt"):
            for optimized in (False, True):
                with self.subTest(exception=exception, optimized=optimized):
                    bootstrap = (
                        "import runpy; from unittest.mock import patch; "
                        f"failure = {exception}({str(self.home)!r}); "
                        "guard = patch('pwd.getpwuid', side_effect=failure); "
                        f"guard.start(); runpy.run_path({str(PROBE)!r}, run_name='__main__')"
                    )
                    result = subprocess.run(
                        [sys.executable] + (["-O"] if optimized else []) + ["-c", bootstrap],
                        capture_output=True, env=self.env, timeout=30, check=False,
                    )
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

    def test_plain_receipts_bind_original_artifacts(self):
        required = {"id", "kind", "claim", "limitations", "recorded_at_utc", "host", "evidence_class", "artifacts"}
        for name in ("nativestack", "nativestack2604", "stackmeasure2604", "coreutils-2604-upgrade"):
            with self.subTest(receipt=name):
                receipt = json.loads((ROOT / f"evidence/receipts/host-baseline-{name}-20261004.json").read_text())
                self.assertTrue(required <= set(receipt))
                self.assertEqual(receipt["kind"], "host_baseline")
                self.assertEqual(receipt["evidence_class"],
                                 "Independent observation" if name == "coreutils-2604-upgrade" else "local_integration")
                self.assertTrue({"component_id", "component_ids", "stage", "result"}.isdisjoint(receipt))
                for artifact in receipt["artifacts"]:
                    self.assertEqual(artifact["sha256"], hashlib.sha256((ROOT / artifact["path"]).read_bytes()).hexdigest())
                if name == "coreutils-2604-upgrade":
                    self.assertIn("| Independent observation |", (ROOT / "docs/acceptance-evidence-policy.md").read_text())
                    self.assertEqual(receipt["evidence_policy"], "docs/acceptance-evidence-policy.md#identify-what-each-check-proves")
                    self.assertEqual(receipt["host"]["distribution"], "NativeStack2604")
                    self.assertFalse(receipt["source"]["reexecuted"])
                    self.assertEqual(receipt["source"]["files"], ["run.log", "versions-before.txt", "versions-after.txt"])
                else:
                    self.assertEqual(receipt["reachability"]["passwordless_sudo"], "unknown")
                    source = next(a for a in receipt["artifacts"] if a["role"] == "probe_source")
                    self.assertEqual(source["path"], "evidence/artifacts/host-baseline-20261004/host-baseline-probe-"
                                     + ("r1" if name == "nativestack" else "r0") + ".txt")
                    observation = next(a for a in receipt["artifacts"] if a["role"] == "observation")
                    data = json.loads((ROOT / observation["path"]).read_text())
                    self.assertEqual(data["probe"]["output"], source["sha256"])
                    if name == "nativestack":
                        self.assertEqual(receipt["host"]["host_id"], "nativestack-5975wx-20260925")
                    else:
                        self.assertEqual(receipt["reachability"]["gdb"], "unobserved")
                        expected = {
                            "nativestack2604": "a9ef297bef7ad864cee212ca34c30e76e0da7770fd3d746ab344edf2bd2e1b46",
                            "stackmeasure2604": "0d771af61bf75d07cbc6bf428b82652b0d5cd3a030ff3a4e83e28439b5ea66c6",
                        }
                        self.assertEqual(observation["sha256"], expected[name])
        self.assertFalse((ROOT / "evidence/hosts/nativestack-2404-20261004").exists())

    def test_historical_receipts_do_not_attest_transport_or_package_state(self):
        for name in ("nativestack", "nativestack2604", "stackmeasure2604"):
            with self.subTest(receipt=name):
                receipt = json.loads((ROOT / f"evidence/receipts/host-baseline-{name}-20261004.json").read_text())
                identity = receipt["probe_identity"]
                self.assertEqual(identity["basis"], "self_reported_canonical_source")
                self.assertIsNone(identity["executed_input_sha256"])
                self.assertFalse(identity["executed_input_verified"])
                self.assertEqual(receipt["package_query_status"], "unrecorded")
                self.assertTrue(any("db:Status-Status" in limitation for limitation in receipt["limitations"]))

    def test_decision_counts_match_retained_artifacts(self):
        decision = (ROOT / "docs/decisions/2026-10-04-host-baseline-recorder.md").read_text()
        for name in ("nativestack-2404", "nativestack2604", "stackmeasure2604"):
            with self.subTest(artifact=name):
                data = json.loads((ROOT / f"evidence/artifacts/host-baseline-20261004/{name}.json").read_text())
                records = list(observations(data))
                counts = Counter(record["exit"] for record in records)
                dates_ok = sum(record["date_utc"]["exit"] == 0 for record in records)
                self.assertIn(f"| `{name}.json` | {len(records)} | {counts[0]} | {counts[1]} | {counts[127]} | {dates_ok} |", decision)

    def test_receipt_amendments_date_changes_and_preserve_prior_values(self):
        for name in ("nativestack", "nativestack2604", "stackmeasure2604", "coreutils-2604-upgrade"):
            with self.subTest(receipt=name):
                receipt = json.loads((ROOT / f"evidence/receipts/host-baseline-{name}-20261004.json").read_text())
                self.assertEqual(receipt["recorded_at_utc"], "2026-10-05T01:47:45Z")
                amendment = next(a for a in receipt["amendments"] if a["ref"] == "PR #710 t1 (7ec3f2a5f) and t2")
                self.assertRegex(amendment["amended_at_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
                self.assertGreater(amendment["amended_at_utc"], receipt["recorded_at_utc"])
                fields = set(amendment["changed_fields"])
                self.assertIn("limitations", fields)
                if name == "coreutils-2604-upgrade":
                    self.assertTrue({"evidence_class", "evidence_policy"} <= fields)
                    self.assertEqual(amendment["prior_values"], {"evidence_class": "local_integration"})
                else:
                    self.assertTrue({"probe_identity", "package_query_status"} <= fields)
                    if name == "nativestack":
                        self.assertIn("artifacts[probe_source].path", fields)
                        self.assertEqual(amendment["prior_values"], {"artifacts[probe_source].path": "tools/adoption/host_baseline_probe.py"})
                    else:
                        self.assertEqual(amendment["prior_values"], {})

    def test_guide_distinguishes_source_round_and_amendment_stamp(self):
        guide = " ".join((ROOT / "tools/adoption/host-baseline.md").read_text().split())
        self.assertIn("coordinator's command for the two r0 26.04 captures (repair round r1)", guide)
        self.assertIn("amendments[].amended_at_utc", guide)
        self.assertIn("initial receipt assembly", guide)


if __name__ == "__main__":
    unittest.main()
