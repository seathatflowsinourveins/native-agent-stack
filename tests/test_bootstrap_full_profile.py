"""adoption/bootstrap-linux.sh --configure-full-profile.

- Usage: an unknown --skip step, --skip or --host without the flag, a missing --host and a host without a value file
  exit 2 before anything else runs.
- The real script refuses (exit 1, both commits printed) from a checkout that is not at its origin's main, before it
  reads the manifest and before its first host change; at origin's main it goes on, and without the flag it never asks
  git. The origin is a local bare repository, so no network is used. The first host change is the system-package step
  (`sudo apt-get`): with `sudo` and `dpkg-query` stubbed on PATH, a refused checkout (ahead of its origin, or with an
  unreachable one) leaves the stub's call log empty, while a checkout at origin's main, and any checkout without the
  flag, do reach the stubbed package commands (so an empty log is the ordering, not a stub that never ran); a host
  without git is refused with the instruction to install it, again with an empty log.
- The steps run in the order the script declares, each once; a failing step is recorded and the rest still run.
- The step functions, extracted verbatim as tests/test_adoption_bootstrap.py extracts install_native, run against
  stubs: the Codex lane prepares the Codex home, then applies exactly the hashes its own dry run printed (in the format
  apply_codex_lane.py prints), with the installed codex, the host file's HOST_PATH and the ecosystem bin directory
  first on PATH, and applies nothing after a refusal or without them; the skills step installs the pinned CLI through
  install_npm, whose checksum exit stays inside the step; the login-shell step fails when claude is not the ecosystem
  launcher.
- The Codex lane step against the real render_config.py, codex_home.py and apply_codex_lane.py dry run (a stub codex
  that reports the pinned version), in a temporary HOME: apply_codex_lane.py's own preconditions report config.toml,
  HOST_PATH and features.daemon_auto_start ok for (a) a fresh HOME with no ~/.codex, which gets the render without the
  source host's [projects] and [hooks.state] trust state (0600 in a 0700 home), (b) a home holding the whole render,
  left byte for byte, and (c) a config.toml without the feature, set through `codex features disable` after a backup;
  a running codex stops (c) with nothing written. The dry run still refuses there (no pinned context-mode or node
  under the example host's ecosystem root), so nothing is applied.
- codex_home.py's cut of the trust state, on the real rendered template: exactly those tables go, every other value
  stays, and an ecosystem root that is not the render's, or a daemon_auto_start that is not the boolean false, is
  refused with nothing written.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "adoption/bootstrap-linux.sh"
TEXT = SCRIPT.read_text(encoding="utf-8")
BASH = shutil.which("bash")
GIT = shutil.which("git")
JQ = shutil.which("jq")
PGREP = shutil.which("pgrep")
H1, H2 = "a" * 64, "b" * 64
sys.path.insert(0, str(ROOT / "tools" / "adoption"))
import codex_home  # noqa: E402
import render_config  # noqa: E402

# The committed example host (read at run time, never restated here): its ECO_ROOT holds no pinned context-mode or
# node, so apply_codex_lane.py's dry run always stops at its preconditions before any rehearsal or write.
EXAMPLE = json.loads((ROOT / "adoption/hosts/example.json").read_text(encoding="utf-8"))
PINNED_CODEX = re.search(r'(?m)^CODEX_VERSION = "([^"]+)"$',
                         (ROOT / "tools/adoption/apply_codex_lane.py").read_text(encoding="utf-8")).group(1)


def os_release_id() -> str:
    try:
        return re.search(r'(?m)^ID="?([^"\n]*)', Path("/etc/os-release").read_text()).group(1)
    except (OSError, AttributeError):
        return ""


RUNS_THE_SCRIPT = unittest.skipUnless(
    sys.platform.startswith("linux") and platform.machine() == "x86_64" and os.geteuid() != 0
    and os_release_id() in ("ubuntu", "debian")
    and all(shutil.which(tool) for tool in ("curl", "git", "tar", "sha256sum", "realpath", "flock", "jq", "mktemp")),
    "the script's own guards need a non-root Ubuntu/Debian x86_64 host with its prerequisites")


def function(name: str, text: str = TEXT) -> str:
    match = re.search(rf"(?ms)^{name}\(\) \{{.*?^\}}$", text)
    if match is None:
        raise AssertionError(f"{name} not found in {SCRIPT}")
    return match.group(0)


def position(fragment: str, text: str = TEXT) -> int:
    at = text.find(fragment)
    if at < 0:
        raise AssertionError(f"{fragment!r} not found in {SCRIPT}")
    return at


def clean_env(**extra) -> dict:
    return {**{key: value for key, value in os.environ.items() if not key.startswith("GIT_")}, **extra}


def run_script(script: Path, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, str(script), *args], capture_output=True, text=True, timeout=120,
                          env=env or clean_env(), stdin=subprocess.DEVNULL)


def harness(body: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, "-c", "set -Eeuo pipefail\n" + body], capture_output=True, text=True, timeout=60,
                          env=env or clean_env())


class UsageTests(unittest.TestCase):
    @unittest.skipUnless(BASH, "requires Bash")
    def test_claude_md_caller_explicitly_preserves_the_full_profile_home_scope(self):
        line = next(line for line in TEXT.splitlines() if "full_profile_run claude-md python3" in line)
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            custom = Path(temporary) / "custom-claude"
            for value in ("", str(custom)):
                result = harness('repo_root=' + shlex.quote(str(ROOT)) +
                                 '\nfull_profile_run() { shift; "$@"; }\n' + line,
                                 env=clean_env(HOME=str(home), CLAUDE_CONFIG_DIR=value))
                self.assertEqual(result.returncode, 0, result.stderr)
                target = home / ".claude/CLAUDE.md"
                self.assertIn("native-agent-stack:claude-user-instructions:begin", target.read_text())
                self.assertFalse(custom.exists())

    def test_usage_errors_exit_two_before_anything_runs(self):
        cases = (
            (["--configure-full-profile", "--skip", "claude-settings,codex-lane,nope"], "Unknown --skip step: nope"),
            (["--skip", "claude-md"], "apply only with --configure-full-profile"),
            (["--host", "example"], "apply only with --configure-full-profile"),
            (["--configure-full-profile"], "needs --host <name>"),
            (["--configure-full-profile", "--host", "../example"], "Invalid --host name"),
            (["--configure-full-profile", "--host", "no-such-host-file"], "No host value file"),
        )
        for args, message in cases:
            with self.subTest(args=args):
                result = run_script(SCRIPT, "--profile", "foundation-cpu", "--skip-system-packages", *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(message, result.stderr)

    def test_skipping_both_rendered_steps_needs_no_host_and_help_lists_the_steps(self):
        steps = re.search(r"(?m)^full_profile_steps=\(([^)]*)\)$", TEXT).group(1).split()
        result = run_script(SCRIPT, "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("  " + " ".join(steps), result.stdout)
        self.assertIn("--configure-full-profile --host <name>", result.stdout)


class StepOrderTests(unittest.TestCase):
    def test_the_steps_run_once_each_in_the_declared_order(self):
        steps = re.search(r"(?m)^full_profile_steps=\(([^)]*)\)$", TEXT).group(1).split()
        self.assertEqual(steps, ["claude-profile", "claude-settings", "claude-md", "skills", "codex-lane",
                                 "path-block", "login-shell"])
        self.assertEqual(re.findall(r"(?m)^  full_profile_run ([a-z-]+) ", TEXT), steps)

    def test_the_full_profile_follows_the_unchanged_report_step(self):
        # tests/test_adoption_version_probes.py keeps version_probe_seconds=30 .. "  exit 5\nfi\n" identical in both
        # scripts; the flag's work comes after that region, so a failed version report stops before it.
        report_end = TEXT.index("  exit 5\nfi\n", TEXT.index("version_probe_seconds=30\n"))
        self.assertGreater(TEXT.index('if [[ "$configure_full_profile" == 1 ]]; then\n  command -v python3'),
                           report_end)

    def test_the_origin_main_check_comes_before_the_system_packages_and_every_other_host_change(self):
        # The source order, which holds on every host (the stubbed runs below need a Debian one): the git prerequisite
        # and the one origin/main comparison, then the system-package step (the first host change), then the first
        # directory the script creates.
        self.assertEqual(TEXT.count("ls-remote origin refs/heads/main"), 1)
        origin_check = position('git -C "$repo_root" ls-remote origin refs/heads/main')
        git_prerequisite = position("command -v git >/dev/null")
        system_packages = position("sudo apt-get update")
        first_directory = position('mkdir -p "$ecosystem_root"')
        self.assertLess(git_prerequisite, origin_check)
        self.assertLess(origin_check, system_packages)
        self.assertLess(system_packages, first_directory)

    def test_a_failing_step_is_recorded_and_the_rest_still_run(self):
        body = ("full_profile_skips=(skills)\nfull_profile_failed=()\n" + function("full_profile_selected") + "\n"
                + function("full_profile_run") + "\n"
                "full_profile_run claude-md false\nfull_profile_run skills false\nfull_profile_run path-block true\n"
                'printf "failed=%s\\n" "${full_profile_failed[*]}"\n')
        result = harness(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-- claude-md: FAILED (exit 1)", result.stderr)
        self.assertIn("-- skills: skipped (--skip skills)", result.stdout)
        self.assertIn("-- path-block --", result.stdout)
        self.assertIn("failed=claude-md\n", result.stdout)


@unittest.skipUnless(BASH and GIT, "needs bash and git")
class OriginMainGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = base = Path(temporary.name)
        self.repo, origin = base / "checkout", base / "origin.git"
        (self.repo / "adoption").mkdir(parents=True)
        self.script = self.repo / "adoption/bootstrap-linux.sh"
        self.script.write_text(TEXT, encoding="utf-8")
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.commit("first")
        subprocess.run([GIT, "init", "-q", "--bare", "-b", "main", str(origin)], check=True, env=clean_env())
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "origin", "main")
        self.env = clean_env(ECO_INSTALL_ROOT=str(base / "eco"))
        self.flags = ["--profile", "foundation-cpu", "--skip-system-packages", "--configure-full-profile",
                      "--skip", "claude-settings,codex-lane"]
        self.package_flags = [flag for flag in self.flags if flag != "--skip-system-packages"]

    def git(self, *args: str) -> str:
        return subprocess.run([GIT, "-C", str(self.repo), *args], check=True, capture_output=True, text=True,
                              env=clean_env()).stdout.strip()

    def commit(self, message: str) -> None:
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
                 "commit", "-q", "--allow-empty", "-m", message)

    @RUNS_THE_SCRIPT
    def test_a_checkout_ahead_of_origin_main_is_refused_with_both_commits_printed(self):
        origin_main = self.git("rev-parse", "HEAD")
        self.commit("local only")
        head = self.git("rev-parse", "HEAD")
        result = run_script(self.script, *self.flags, env=self.env)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"This checkout (git rev-parse HEAD):        {head}", result.stdout)
        self.assertIn(f"origin main (git ls-remote origin main):   {origin_main}", result.stdout)
        self.assertIn("Refusing --configure-full-profile: this checkout is not at origin/main", result.stderr)
        self.assertNotIn("Missing manifest", result.stderr)
        self.assertFalse(Path(self.env["ECO_INSTALL_ROOT"]).exists())

    @RUNS_THE_SCRIPT
    def test_a_checkout_at_origin_main_goes_on_and_no_flag_never_asks_git(self):
        result = run_script(self.script, *self.flags, env=self.env)
        self.assertNotIn("Refusing --configure-full-profile", result.stderr)
        self.assertIn("Missing manifest", result.stderr)  # the next check, in this manifest-less checkout
        self.commit("local only")
        result = run_script(self.script, "--profile", "foundation-cpu", "--skip-system-packages", env=self.env)
        self.assertNotIn("origin main", result.stdout)
        self.assertIn("Missing manifest", result.stderr)

    @RUNS_THE_SCRIPT
    def test_an_unreachable_origin_is_refused(self):
        self.git("remote", "set-url", "origin", str(self.repo.parent / "gone.git"))
        result = run_script(self.script, *self.flags, env=self.env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("origin main (git ls-remote origin main):   unknown", result.stdout)
        self.assertIn("not at origin/main", result.stderr)

    # The system-package step is the script's first host change. Its commands are stubs: dpkg-query reports every
    # package missing and sudo (how the script runs apt-get) appends its command line to a log and does nothing else,
    # so a run that reaches the step leaves a record and the host is never touched.
    def package_stubs(self) -> tuple:
        stubs, log = self.base / "stubs", self.base / "package-calls.log"
        stubs.mkdir(exist_ok=True)
        (stubs / "dpkg-query").write_text("#!/bin/sh\nexit 1\n")
        (stubs / "sudo").write_text(f"#!/bin/sh\nprintf 'sudo %s\\n' \"$*\" >> {shlex.quote(str(log))}\nexit 0\n")
        for name in ("dpkg-query", "sudo"):
            (stubs / name).chmod(0o755)
        log.unlink(missing_ok=True)
        return stubs, log

    def stubbed_env(self, stubs: Path) -> dict:
        return clean_env(PATH=f"{stubs}{os.pathsep}{os.environ['PATH']}", ECO_INSTALL_ROOT=str(self.base / "eco"))

    @staticmethod
    def calls(log: Path) -> list:
        return log.read_text().splitlines() if log.exists() else []

    @RUNS_THE_SCRIPT
    def test_a_checkout_ahead_of_origin_main_is_refused_before_any_package_command_runs(self):
        stubs, log = self.package_stubs()
        self.commit("local only")
        result = run_script(self.script, *self.package_flags, env=self.stubbed_env(stubs))
        self.assertEqual(self.calls(log), [], "a package command ran before the origin/main check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Refusing --configure-full-profile: this checkout is not at origin/main", result.stderr)
        self.assertFalse((self.base / "eco").exists())

    @RUNS_THE_SCRIPT
    def test_an_unreachable_origin_is_refused_before_any_package_command_runs(self):
        stubs, log = self.package_stubs()
        self.git("remote", "set-url", "origin", str(self.base / "gone.git"))
        result = run_script(self.script, *self.package_flags, env=self.stubbed_env(stubs))
        self.assertEqual(self.calls(log), [], "a package command ran before the origin/main check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("origin main (git ls-remote origin main):   unknown", result.stdout)
        self.assertIn("not at origin/main", result.stderr)
        self.assertFalse((self.base / "eco").exists())

    @RUNS_THE_SCRIPT
    def test_a_host_without_git_is_told_to_install_it_before_any_package_command_runs(self):
        stubs, log = self.package_stubs()
        for tool in ("uname", "dirname"):  # all the script runs before the check; git is the one tool left out
            (stubs / tool).symlink_to(shutil.which(tool))
        result = run_script(self.script, *self.package_flags,
                            env=clean_env(PATH=str(stubs), ECO_INSTALL_ROOT=str(self.base / "eco")))
        self.assertEqual(self.calls(log), [], "a package command ran before the git prerequisite check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Refusing --configure-full-profile: git is not installed", result.stderr)
        self.assertIn("Install git first", result.stderr)
        self.assertNotIn("origin main (git ls-remote", result.stdout)
        self.assertFalse((self.base / "eco").exists())

    # The controls for the empty logs above: the same stubs record the package commands of a run that is allowed to
    # reach the step, and the default path (no flag) keeps its order, package step first and git never asked.
    @RUNS_THE_SCRIPT
    def test_at_origin_main_and_without_the_flag_the_same_stubs_do_log_the_package_commands(self):
        stubs, log = self.package_stubs()
        env = self.stubbed_env(stubs)
        cases = (("--configure-full-profile at origin main", self.package_flags, True),
                 ("no flag, checkout ahead of origin main", ["--profile", "foundation-cpu"], False))
        for label, flags, at_origin_main in cases:
            with self.subTest(label):
                log.unlink(missing_ok=True)
                if not at_origin_main:
                    self.commit("local only")
                result = run_script(self.script, *flags, env=env)
                self.assertIn("Missing manifest", result.stderr)  # the next check, in this manifest-less checkout
                self.assertNotIn("Refusing --configure-full-profile", result.stderr)
                self.assertEqual(("origin main (git ls-remote origin main)" in result.stdout), at_origin_main)
                calls = self.calls(log)
                self.assertEqual(len(calls), 2, calls)
                self.assertEqual(calls[0], "sudo apt-get update")
                self.assertTrue(calls[1].startswith("sudo apt-get install -y --no-install-recommends "), calls[1])


@unittest.skipUnless(BASH and JQ, "needs bash and jq")
class StepFunctionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.log = self.base / "calls.log"

    def calls(self) -> list:
        return self.log.read_text().splitlines() if self.log.exists() else []

    # apply_codex_lane.py cmd_plan prints the --apply command this way; the stub below prints the same line.
    def test_the_stub_plan_line_is_the_one_apply_codex_lane_prints(self):
        source = (ROOT / "tools/adoption/apply_codex_lane.py").read_text(encoding="utf-8")
        for fragment in ('print(f"  python3 {Path(__file__).resolve().relative_to(ROOT)} --apply"',
                         '+ (f" --eco-root {plan.eco_root}" if args.eco_root else "")',
                         "+ (f\" --host-path '{plan.host_path}'\" if args.host_path else \"\")",
                         '+ f" --expect-config-sha256 {sha256_bytes(plan.config_bytes)} --expect-agents-sha256 {agents_sha}")',
                         'codex = args.codex or shutil.which("codex")'):
            self.assertIn(fragment, source)

    def codex_lane(self, plan: str, status: int, home_status: int = 0,
                   host: dict | None = None) -> subprocess.CompletedProcess:
        """The step against stubs: each codex_home.py and apply_codex_lane.py call is logged with the first PATH entry
        it saw."""
        (self.base / "plan.txt").write_text(plan)
        hosts = self.base / "adoption/hosts"
        hosts.mkdir(parents=True, exist_ok=True)
        (hosts / "h.json").write_text(json.dumps({"HOST_PATH": "/usr/bin:/bin"} if host is None else host))
        body = (f"repo_root={shlex.quote(str(self.base))}\necosystem_root=/opt/eco\nbin_dir=/opt/eco/bin\n"
                f"stage_dir={shlex.quote(str(self.base))}\nfull_profile_host=h\nfull_profile_rendered=\n"
                'python3() {\n  local tool="${1##*/}"\n  shift\n  case "$tool" in\n'
                '    render_config.py) mkdir -p "$stage_dir/rendered" ;;\n'
                f'    codex_home.py) printf "%s PATH=%s %s\\n" "$tool" "${{PATH%%:*}}" "$*" >> {shlex.quote(str(self.log))}; '
                f'return {home_status} ;;\n'
                f'    apply_codex_lane.py) printf "%s PATH=%s %s\\n" "$tool" "${{PATH%%:*}}" "$*" >> {shlex.quote(str(self.log))}; '
                f'if [[ " $* " != *" --apply "* ]]; then cat {shlex.quote(str(self.base / "plan.txt"))}; return {status}; fi ;;\n'
                '  esac\n}\n'
                + function("full_profile_render") + "\n" + function("full_profile_codex_lane") + "\n"
                'rc=0; full_profile_codex_lane || rc=$?; printf "rc=%s\\n" "$rc"\n')
        return harness(body)

    def prepared(self) -> str:
        return (f"codex_home.py PATH=/opt/eco/bin --rendered {self.base}/rendered/codex.config.toml "
                "--eco-root /opt/eco --codex /opt/eco/bin/codex")

    def test_the_codex_lane_prepares_the_home_then_applies_exactly_the_hashes_its_dry_run_printed(self):
        lane = "--codex /opt/eco/bin/codex --eco-root /opt/eco --host-path /usr/bin:/bin"
        for agents in (H2, "absent"):
            with self.subTest(agents=agents):
                self.log.unlink(missing_ok=True)
                line = (f"  python3 tools/adoption/apply_codex_lane.py --apply --eco-root /opt/eco --host-path "
                        f"'/usr/bin:/bin' --expect-config-sha256 {H1} --expect-agents-sha256 {agents}")
                result = self.codex_lane(f"DRY RUN\nresult: rehearsal passed. Apply ... with:\n{line}\nworkers ...\n", 0)
                self.assertIn("rc=0", result.stdout, result.stderr)
                self.assertEqual(self.calls(), [
                    self.prepared(), f"apply_codex_lane.py PATH=/opt/eco/bin {lane}",
                    f"apply_codex_lane.py PATH=/opt/eco/bin --apply {lane} --expect-config-sha256 {H1} "
                    f"--expect-agents-sha256 {agents}"])

    def test_the_codex_lane_applies_nothing_after_a_refusal_or_without_both_hashes(self):
        dry_run = "apply_codex_lane.py PATH=/opt/eco/bin --codex /opt/eco/bin/codex --eco-root /opt/eco --host-path /usr/bin:/bin"
        for plan, status, rc in (("  [fail] codex processes: 1 running\nrefused\n", 2, "rc=2"),
                                 ("result: rehearsal passed\n", 0, "rc=1"),
                                 (f"  python3 tools/adoption/apply_codex_lane.py --apply --expect-config-sha256 {H1}\n", 0,
                                  "rc=1")):
            with self.subTest(plan=plan):
                self.log.unlink(missing_ok=True)
                result = self.codex_lane(plan, status)
                self.assertIn(rc, result.stdout, result.stderr)
                self.assertEqual(self.calls(), [self.prepared(), dry_run])

    def test_a_home_the_helper_refuses_or_a_host_file_without_host_path_runs_no_lane(self):
        result = self.codex_lane("unused\n", 0, home_status=3)
        self.assertIn("rc=3", result.stdout, result.stderr)
        self.assertEqual(self.calls(), [self.prepared()])
        self.log.unlink()
        for host in ({}, {"HOST_PATH": ""}):
            with self.subTest(host=host):
                result = self.codex_lane("unused\n", 0, host=host)
                self.assertIn("rc=1", result.stdout, result.stderr)
                self.assertIn("adoption/hosts/h.json has no HOST_PATH", result.stderr)
                self.assertEqual(self.calls(), [])

    def skills(self, install_npm: str) -> subprocess.CompletedProcess:
        manifest = json.loads((ROOT / "adoption/skills/manifest.json").read_text(encoding="utf-8"))["cli"]
        self.cli = manifest
        log = shlex.quote(str(self.log))
        body = (f"repo_root={shlex.quote(str(ROOT))}\necosystem_root={shlex.quote(str(self.base / 'eco'))}\n"
                f'python3() {{ printf "python3 %s\\n" "$*" >> {log}; }}\n'
                f'install_npm() {{ printf "install_npm %s\\n" "$*" >> {log}; {install_npm}; }}\n'
                + function("full_profile_skills") + "\n"
                'rc=0; full_profile_skills || rc=$?; printf "rc=%s\\n" "$rc"\n')
        return harness(body)

    def test_the_skills_step_installs_the_pinned_cli_then_the_manifest(self):
        result = self.skills("true")
        self.assertIn("rc=0", result.stdout, result.stderr)
        skills_bin = self.base / "eco" / f"tools/skills-{self.cli['version']}/bin/skills"
        self.assertEqual(self.calls(), [
            f"install_npm skills {self.cli['version']} {self.cli['tarball']} {self.cli['sha256']} true",
            f"python3 {ROOT}/tools/adoption/install_skills.py --skills-bin {skills_bin}"])

    def test_a_checksum_exit_inside_install_npm_fails_only_the_skills_step(self):
        result = self.skills("exit 1")
        self.assertIn("rc=1", result.stdout, result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def login_shell(self, report: dict, status: int) -> subprocess.CompletedProcess:
        bin_dir = self.base / "bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "uv").write_text(f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(json.dumps(report))}\nexit {status}\n")
        (bin_dir / "uv").chmod(0o755)
        body = (f"repo_root={shlex.quote(str(ROOT))}\necosystem_root=/opt/eco\nbin_dir={shlex.quote(str(bin_dir))}\n"
                "profile_id=foundation-cpu\n" + function("full_profile_login_shell") + "\n"
                'rc=0; full_profile_login_shell || rc=$?; printf "rc=%s\\n" "$rc"\n')
        return harness(body)

    def test_the_login_shell_step_fails_unless_claude_is_the_ecosystem_launcher(self):
        launcher = {"resolution": "ecosystem_launcher", "path": "$ECO_ROOT/bin/claude", "is_ecosystem_launcher": True,
                    "launcher_sha256": H1}
        other = {**launcher, "resolution": "not_found", "path": None, "is_ecosystem_launcher": False}
        for resolution, status, rc in ((launcher, 0, "rc=0"), (other, 0, "rc=1"), (launcher, 2, "rc=2")):
            with self.subTest(resolution=resolution["resolution"], status=status):
                result = self.login_shell({"status": "x", "login_shell": {"profile_read": True},
                                           "launcher_resolution": resolution, "profiles": []}, status)
                self.assertIn(rc, result.stdout, result.stderr)
                self.assertIn('"launcher_resolution"', result.stdout)
                if rc == "rc=1":
                    self.assertIn("is not the ecosystem launcher", result.stderr)


@unittest.skipUnless(BASH and JQ and PGREP, "needs bash, jq and pgrep")
class CodexLaneOnARealHomeTests(unittest.TestCase):
    """full_profile_codex_lane, extracted verbatim, with the real render_config.py (--host example), codex_home.py and
    apply_codex_lane.py dry run in a temporary HOME. Only codex and pgrep are stubs, in the bin directory the step puts
    first on PATH: codex answers --version with the lane's pin, applies `features disable daemon_auto_start` to
    $CODEX_HOME/config.toml the way Codex 0.157.1 does for a file without a [features] table, and fails any other
    command, so no rehearsal could run; pgrep reports a running codex only when a test asks, so the host's own Codex
    sessions do not decide the result."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.codex_home = self.home / ".codex"
        self.config = self.codex_home / "config.toml"
        self.stage = self.base / "stage"
        self.stage.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.codex_log = self.base / "codex.log"
        self.codex_log.write_text("")
        codex = self.bin / "codex"
        codex.write_text("#!/bin/sh\n"
                         f'printf "%s\\n" "$*" >> {shlex.quote(str(self.codex_log))}\n'
                         'case "$*" in\n'
                         f'  --version) echo "codex-cli {PINNED_CODEX}" ;;\n'
                         '  "features disable daemon_auto_start")\n'
                         "    printf '\\n[features]\\ndaemon_auto_start = false\\n' >> \"$CODEX_HOME/config.toml\" ;;\n"
                         "  *) exit 64 ;;\n"
                         "esac\n")
        codex.chmod(0o755)
        self.running = self.base / "codex-is-running"
        pgrep = self.bin / "pgrep"
        pgrep.write_text("#!/bin/sh\n"
                         f'if [ "$*" = "-x codex" ] && [ -e {shlex.quote(str(self.running))} ]; then echo 4242; exit 0; fi\n'
                         "exit 1\n")
        pgrep.chmod(0o755)

    def run_step(self, text: str = TEXT) -> subprocess.CompletedProcess:
        body = (f"repo_root={shlex.quote(str(ROOT))}\necosystem_root={shlex.quote(EXAMPLE['ECO_ROOT'])}\n"
                f"bin_dir={shlex.quote(str(self.bin))}\nstage_dir={shlex.quote(str(self.stage))}\n"
                "full_profile_host=example\nfull_profile_rendered=\n"
                + function("full_profile_render", text) + "\n" + function("full_profile_codex_lane", text) + "\n"
                'rc=0; full_profile_codex_lane || rc=$?; printf "rc=%s\\n" "$rc"\n')
        env = {key: value for key, value in clean_env().items() if key != "CODEX_HOME"}
        env.update(HOME=str(self.home), XDG_STATE_HOME=str(self.base / "state"), TMPDIR=str(self.base))
        return harness(body, env)

    def assert_the_lanes_preconditions_hold(self, result: subprocess.CompletedProcess) -> None:
        """apply_codex_lane.py's own precondition lines for the three the review named, then its refusal: the
        example host's ecosystem root has no pinned context-mode start.mjs, so nothing is rehearsed or applied."""
        out = result.stdout
        self.assertIn(f"  [ok] config.toml: {self.config} present\n", out, result.stderr)
        self.assertIn(f"  [ok] HOST_PATH: {EXAMPLE['HOST_PATH']}\n", out)
        self.assertIn("  [ok] features.daemon_auto_start: false\n", out)
        self.assertIn("  [fail] context-mode start.mjs: ", out)
        self.assertIn("result: apply would refuse", out)
        self.assertIn("rc=2", out)
        self.assertIn("The Codex lane dry run refused (exit 2); nothing applied.", result.stderr)
        self.assertNotIn("run record:", out)
        self.assertFalse((self.base / "state").exists())
        self.assertFalse(any(line not in ("--version", "features disable daemon_auto_start")
                             for line in self.codex_log.read_text().splitlines()))

    def test_a_fresh_home_gets_the_render_without_its_trust_state_and_meets_the_lanes_preconditions(self):
        self.assertFalse(self.codex_home.exists())
        result = self.run_step()
        self.assert_the_lanes_preconditions_hold(result)
        rendered = tomllib.loads((self.stage / "rendered/codex.config.toml").read_text(encoding="utf-8"))
        grants, approvals = len(rendered["projects"]), len(rendered["hooks"]["state"])
        self.assertGreater(grants * approvals, 0, "the render no longer carries trust state to leave out")
        written = tomllib.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(written, codex_home.expected_without_trust(rendered))
        self.assertNotIn("projects", written)
        self.assertNotIn("hooks", written)
        self.assertEqual(stat.S_IMODE(self.codex_home.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertIn(f"{grants} [projects] trust grant(s) and {approvals} [hooks.state] approval(s) left out",
                      result.stdout)
        self.assertNotIn("features disable daemon_auto_start", self.codex_log.read_text())

    def test_a_home_holding_the_whole_render_is_left_byte_for_byte(self):
        self.codex_home.mkdir(mode=0o700)
        values = render_config.load_host_values("example")
        self.config.write_text(render_config.render_one(render_config.TEMPLATE_FILES["codex.config.toml"], values),
                               encoding="utf-8")
        before = self.config.read_bytes()
        result = self.run_step()
        self.assert_the_lanes_preconditions_hold(result)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertIn("kept; features.daemon_auto_start is already false", result.stdout)
        self.assertEqual([path.name for path in self.codex_home.iterdir()], ["config.toml"])  # no backup
        self.assertNotIn("features disable daemon_auto_start", self.codex_log.read_text())

    def test_a_config_without_the_feature_gets_it_through_codex_after_a_backup(self):
        self.codex_home.mkdir(mode=0o700)
        original = '# ours\nmodel = "x"\n\n[projects."/opt/p"]\ntrust_level = "trusted"\n'
        self.config.write_text(original, encoding="utf-8")
        result = self.run_step()
        self.assert_the_lanes_preconditions_hold(result)
        self.assertIn("features disable daemon_auto_start", self.codex_log.read_text().splitlines())
        backups = [path for path in self.codex_home.iterdir() if path.name.startswith("config.toml.bak.")]
        self.assertEqual([path.read_text(encoding="utf-8") for path in backups], [original])
        self.assertTrue(self.config.read_text(encoding="utf-8").startswith(original))
        # This host's own trust grant is its operator's: it stays.
        self.assertEqual(tomllib.loads(self.config.read_text(encoding="utf-8"))["projects"],
                         {"/opt/p": {"trust_level": "trusted"}})

    def test_a_running_codex_stops_the_feature_write_and_the_lane(self):
        # apply_codex_lane.py --apply refuses while codex runs; the feature write before it does too.
        self.codex_home.mkdir(mode=0o700)
        original = '# ours\nmodel = "x"\n'
        self.config.write_text(original, encoding="utf-8")
        self.running.touch()
        result = self.run_step()
        self.assertIn("rc=3", result.stdout, result.stderr)
        self.assertIn("1 codex process(es) running (pids 4242)", result.stderr)
        self.assertEqual(self.config.read_text(encoding="utf-8"), original)
        self.assertEqual([path.name for path in self.codex_home.iterdir()], ["config.toml"])  # no backup either
        self.assertNotIn("features disable", self.codex_log.read_text())
        self.assertNotIn("Codex worker lane for", result.stdout)  # the lane's dry run never started


class CodexHomeCutTests(unittest.TestCase):
    """codex_home.py's cut of the trust state, and its refusals, which write nothing."""

    def setUp(self):
        self.values = render_config.load_host_values("example")
        self.rendered = render_config.render_one(render_config.TEMPLATE_FILES["codex.config.toml"], self.values)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)

    def main(self, rendered: str, eco_root: str, codex_home_dir: Path) -> tuple[int, str, str]:
        source = self.base / "rendered.toml"
        source.write_text(rendered, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = codex_home.main(["--rendered", str(source), "--eco-root", eco_root, "--codex", "/nonexistent/codex",
                                    "--codex-home", str(codex_home_dir)])
        return code, out.getvalue(), err.getvalue()

    def test_exactly_the_trust_tables_and_the_comments_above_them_go(self):
        text, grants, approvals = codex_home.fresh_config(self.rendered, self.values["ECO_ROOT"])
        source = tomllib.loads(self.rendered)
        self.assertEqual(tomllib.loads(text), codex_home.expected_without_trust(source))
        self.assertEqual((grants, approvals), (len(source["projects"]), len(source["hooks"]["state"])))
        self.assertNotIn("trust_level", text)
        self.assertNotIn("trusted_hash", text)
        self.assertNotIn("# Trust lets Codex load", text)
        # A kept table keeps the comment above it, and every kept line is the render's own, in its order.
        self.assertIn("# Replaced by the session-bound [mcp_servers.context-mode] above.\n"
                      '[plugins."context-mode@context-mode".mcp_servers.context-mode]\n', text)
        body = text.split("step 4).\n", 1)[1]
        rendered_lines = iter(self.rendered.splitlines())
        self.assertTrue(all(any(line == kept for kept in rendered_lines) for line in body.splitlines()))

    def test_a_trust_table_at_either_end_and_a_bracket_inside_an_array_are_cut_correctly(self):
        eco = "/opt/eco"
        text = ('[projects."/a"]\ntrust_level = "trusted"\n\n'
                '[mcp_servers.x]\nargs = [\n  ["nested", "array"],\n]\n\n'
                '[features]\ndaemon_auto_start = false\n\n'
                f'[shell_environment_policy.set]\nPATH = "{eco}/bin:/usr/bin"\n\n'
                '# approvals\n[hooks.state."/b:stop:0:0"]\ntrusted_hash = "sha256:00"\n')
        written, grants, approvals = codex_home.fresh_config(text, eco)
        self.assertEqual((grants, approvals), (1, 1))
        self.assertEqual(tomllib.loads(written), {"mcp_servers": {"x": {"args": [["nested", "array"]]}},
                                                  "features": {"daemon_auto_start": False},
                                                  "shell_environment_policy": {"set": {"PATH": f"{eco}/bin:/usr/bin"}}})
        self.assertTrue(written.endswith(f'\nPATH = "{eco}/bin:/usr/bin"\n'), written[-80:])  # one newline at the end
        # --keep-hook-trust (the new-WSL client-configuration tool's render): the hook approvals stay, the grants go.
        kept, grants, approvals = codex_home.fresh_config(text, eco, keep_hook_trust=True)
        self.assertEqual((grants, approvals), (1, 1))
        self.assertEqual(tomllib.loads(kept), {"mcp_servers": {"x": {"args": [["nested", "array"]]}},
                                               "features": {"daemon_auto_start": False},
                                               "shell_environment_policy": {"set": {"PATH": f"{eco}/bin:/usr/bin"}},
                                               "hooks": {"state": {"/b:stop:0:0": {"trusted_hash": "sha256:00"}}}})
        self.assertNotIn("trust_level", kept)
        self.assertIn("hook approval(s), the hooks whose hashes that tool's map wires, are kept", " ".join(
            line.lstrip("# ") for line in kept.splitlines()[:4]))

    def test_refusals_write_nothing(self):
        broken_string = self.rendered.replace('model = "', 'note = """\n[projects."/x"]\n"""\nmodel = "', 1)
        cases = (
            ("an ecosystem root that is not the render's", self.rendered, "/opt/other-eco",
             "does not start with /opt/other-eco/bin"),
            ("a daemon_auto_start that is not the boolean false",
             self.rendered.replace("daemon_auto_start = false", "daemon_auto_start = 0"), self.values["ECO_ROOT"],
             "does not set features.daemon_auto_start = false"),
            ("a header-like line inside a multi-line string", broken_string, self.values["ECO_ROOT"], "nothing written"),
        )
        for name, rendered, eco_root, message in cases:
            with self.subTest(name):
                target = self.base / name.replace(" ", "-").replace("'", "")
                code, out, err = self.main(rendered, eco_root, target)
                self.assertEqual(code, codex_home.EXIT_REFUSED, out + err)
                self.assertIn(message, err)
                self.assertFalse(target.exists())

    def test_dry_run_writes_nothing_and_an_existing_config_is_never_replaced(self):
        target = self.base / "codex"
        source = self.base / "rendered.toml"
        source.write_text(self.rendered, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = codex_home.main(["--rendered", str(source), "--eco-root", self.values["ECO_ROOT"], "--dry-run",
                                    "--codex-home", str(target)])
        self.assertEqual(code, 0)
        self.assertIn("DRY RUN, would write the rendered user config", out.getvalue())
        self.assertFalse(target.exists())
        target.mkdir()
        (target / "config.toml").write_text("[features]\ndaemon_auto_start = false\n", encoding="utf-8")
        code, out, _ = self.main(self.rendered, self.values["ECO_ROOT"], target)
        self.assertEqual(code, 0)
        self.assertIn("kept; features.daemon_auto_start is already false", out)
        self.assertEqual((target / "config.toml").read_text(encoding="utf-8"), "[features]\ndaemon_auto_start = false\n")
        (target / "config.toml").unlink()
        (target / "config.toml").symlink_to(self.base / "nowhere")
        code, _, err = self.main(self.rendered, self.values["ECO_ROOT"], target)
        self.assertEqual(code, codex_home.EXIT_REFUSED)
        self.assertIn("cannot be read", err)
        self.assertFalse((self.base / "nowhere").exists())


if __name__ == "__main__":
    unittest.main()
