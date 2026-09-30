"""adoption/bootstrap-linux.sh --configure-full-profile.

- Usage: an unknown --skip step, --skip or --host without the flag, a missing --host and a host without a value file
  exit 2 before anything else runs.
- The real script refuses (exit 1, both commits printed) from a checkout that is not at its origin's main, before it
  reads the manifest; at origin's main it goes on, and without the flag it never asks git. The origin is a local bare
  repository, so no network is used.
- The steps run in the order the script declares, each once; a failing step is recorded and the rest still run.
- The step functions, extracted verbatim as tests/test_adoption_bootstrap.py extracts install_native, run against
  stubs: the Codex lane applies exactly the hashes its own dry run printed (in the format apply_codex_lane.py prints)
  and nothing after a refusal or without them; the skills step installs the pinned CLI through install_npm, whose
  checksum exit stays inside the step; the login-shell step fails when claude is not the ecosystem launcher.
"""

import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "adoption/bootstrap-linux.sh"
TEXT = SCRIPT.read_text(encoding="utf-8")
BASH = shutil.which("bash")
GIT = shutil.which("git")
JQ = shutil.which("jq")
H1, H2 = "a" * 64, "b" * 64


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


def function(name: str) -> str:
    match = re.search(rf"(?ms)^{name}\(\) \{{.*?^\}}$", TEXT)
    if match is None:
        raise AssertionError(f"{name} not found in {SCRIPT}")
    return match.group(0)


def clean_env(**extra) -> dict:
    return {**{key: value for key, value in os.environ.items() if not key.startswith("GIT_")}, **extra}


def run_script(script: Path, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, str(script), *args], capture_output=True, text=True, timeout=120,
                          env=env or clean_env(), stdin=subprocess.DEVNULL)


def harness(body: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, "-c", "set -Eeuo pipefail\n" + body], capture_output=True, text=True, timeout=60,
                          env=env or clean_env())


class UsageTests(unittest.TestCase):
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
        base = Path(temporary.name)
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
                         '+ f" --expect-config-sha256 {sha256_bytes(plan.config_bytes)} --expect-agents-sha256 {agents_sha}")'):
            self.assertIn(fragment, source)

    def codex_lane(self, plan: str, status: int) -> subprocess.CompletedProcess:
        (self.base / "plan.txt").write_text(plan)
        body = (f"repo_root={shlex.quote(str(self.base))}\necosystem_root=/opt/eco\nstage_dir={shlex.quote(str(self.base))}\n"
                "full_profile_host=h\nfull_profile_rendered=\n"
                'python3() {\n  case "$1" in\n'
                '    */render_config.py) mkdir -p "$stage_dir/rendered" ;;\n'
                f'    */apply_codex_lane.py) if [[ " $* " == *" --apply "* ]]; then printf "%s\\n" "${{*:2}}" >> {shlex.quote(str(self.log))}; '
                f'else cat {shlex.quote(str(self.base / "plan.txt"))}; return {status}; fi ;;\n  esac\n}}\n'
                + function("full_profile_render") + "\n" + function("full_profile_codex_lane") + "\n"
                'rc=0; full_profile_codex_lane || rc=$?; printf "rc=%s\\n" "$rc"\n')
        return harness(body)

    def test_the_codex_lane_applies_exactly_the_hashes_its_dry_run_printed(self):
        for agents in (H2, "absent"):
            with self.subTest(agents=agents):
                self.log.unlink(missing_ok=True)
                line = (f"  python3 tools/adoption/apply_codex_lane.py --apply --eco-root /opt/eco "
                        f"--expect-config-sha256 {H1} --expect-agents-sha256 {agents}")
                result = self.codex_lane(f"DRY RUN\nresult: rehearsal passed. Apply ... with:\n{line}\nworkers ...\n", 0)
                self.assertIn("rc=0", result.stdout, result.stderr)
                self.assertEqual(self.calls(), [f"--apply --eco-root /opt/eco --expect-config-sha256 {H1} "
                                                f"--expect-agents-sha256 {agents}"])
                self.assertIn("not installed by this step", result.stdout)

    def test_the_codex_lane_applies_nothing_after_a_refusal_or_without_both_hashes(self):
        for plan, status, rc in (("  [fail] codex processes: 1 running\nrefused\n", 2, "rc=2"),
                                 ("result: rehearsal passed\n", 0, "rc=1"),
                                 (f"  python3 tools/adoption/apply_codex_lane.py --apply --expect-config-sha256 {H1}\n", 0,
                                  "rc=1")):
            with self.subTest(plan=plan):
                result = self.codex_lane(plan, status)
                self.assertIn(rc, result.stdout, result.stderr)
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


if __name__ == "__main__":
    unittest.main()
