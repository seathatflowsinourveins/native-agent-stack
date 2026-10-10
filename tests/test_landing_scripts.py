"""Offline tests of the landing scripts in tools/landing: uet_land.sh, nas_land.sh and codex_gate.py.

The scripts merge pull requests, so they are never pointed at GitHub here. Correction #136 (2026-10-10) tested their decision points
with a harness that cuts the decision text out of each script and evaluates it in bash against synthetic inputs and a fake `gh`.
This module is that harness's offline subset, kept beside the one copy of the scripts:

  * verdict files and the GPT_VERDICT block (lg_verdict_file_ok: the harness's 28 synthetic files and six more) and the GATES_DONE rule;
  * the trading-cc-read gate (tcc_read_gate): the description form, the record's last verdict line, the status states;
  * change identity (lg_change_id, lg_same_change) against scratch repositories: binary bytes, mode, names, `--` and `++` lines;
  * the CI line: uet's lg_ci_state on synthetic rollups and nas's check-run line;
  * codex_gate.py: its exit-code precedence on canned API data (subprocess.run and datetime.now are patched);
  * each script end to end with a fake gh, python3 and sleep: the variables and their defaults, the gate path through a symlink and
    a wrapper, and the order in which the gates stop a landing.

A decision site is cut out by the same start and end lines the harness used, so an edit that moves a site fails here loudly instead
of leaving it untested. Everything is synthetic: no network, no gh, no cache files. `jq` is required (the runners have it); when it
is missing the module fails in CI and is skipped elsewhere. The scripts are Linux tools (GNU sha256sum and readlink -f).
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import itertools
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "tools/landing"
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI", "").lower() == "true"
HEAD = "3d8c6344a0e2150d296d84bacff48bc394180e92"
OTHER = "9f8e7d6c5b4a39281706f5e4d3c2b1a098765432"
PR = str(90000000 + os.getpid())  # per process: the nas script makes /var/tmp/nas-land-<pr>-XXXXXX worktrees, which parallel runs must not share
UET_REPO = "seathatflowsinourveins/us-equities-trading"
NAS_REPO = "seathatflowsinourveins/native-agent-stack"


def setUpModule():
    if not sys.platform.startswith("linux"):
        raise unittest.SkipTest("the landing scripts run on the CC's Linux host and need GNU sha256sum and readlink -f")
    missing = [tool for tool in ("bash", "git", "jq", "sha256sum", "readlink", "dirname", "grep", "seq")
               if shutil.which(tool) is None]
    if subprocess.run(["git", "patch-id", "--verbatim"], input="", capture_output=True, text=True).returncode != 0:
        missing.append("git patch-id --verbatim")
    if missing:
        message = f"the landing-script tests need {', '.join(missing)}"
        if IN_CI:
            raise AssertionError(message)
        raise unittest.SkipTest(message)


def q(path):
    return "'" + str(path).replace("'", "'\\''") + "'"


# ---------------------------------------------------------------------------------------------- fake commands
# GitHub-side data are JSON files named by FAKE_STATUSES, FAKE_CHECKRUNS and FAKE_PRVIEW; the scripts' own --jq programs are
# evaluated on them by jq, so the real programs run. Every call is appended to FAKE_LOG.
FAKE_GH = r'''#!/usr/bin/env bash
[ -n "${FAKE_LOG:-}" ] && printf 'gh %s\n' "$*" >> "$FAKE_LOG"
prog=
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  if [ "${args[i]}" = "--jq" ]; then prog=${args[i+1]}; fi
done
case "$1 $2" in
  "api repos/"*)
    case "$2" in
      *"/statuses"*) exec jq -r "$prog" "$FAKE_STATUSES" ;;
      *"/check-runs"*) exec jq -r "$prog" "$FAKE_CHECKRUNS" ;;
      *) exit 1 ;;
    esac ;;
  "api graphql") echo "${FAKE_OPEN_THREADS:-0}"; exit 0 ;;
  "pr view")
    if [ -n "${FAKE_HEADS:-}" ] && [[ "$*" == *headRefOid* ]]; then
      heads=($FAKE_HEADS); n=$(cat "$FAKE_LOG.heads" 2>/dev/null || echo 0); echo $((n + 1)) > "$FAKE_LOG.heads"
      jq --arg h "${heads[$(( n < ${#heads[@]} ? n : ${#heads[@]} - 1 ))]}" '.headRefOid = $h' "$FAKE_PRVIEW" | jq -r "$prog"
      exit "${PIPESTATUS[1]}"
    fi
    exec jq -r "$prog" "$FAKE_PRVIEW" ;;
  "pr ready") exit 0 ;;
  "pr update-branch") exit "${FAKE_UPDATE_RC:-0}" ;;
  "pr merge") echo "merged"; exit "${FAKE_MERGE_RC:-0}" ;;
  *) exit 1 ;;
esac
'''
# codex_gate.py and scripts/validate.py both run as `python3 ...` in the scripts; the log shows which path each call got.
FAKE_PYTHON3 = r'''#!/usr/bin/env bash
printf 'python3 %s\n' "$*" >> "$FAKE_LOG"
case "$*" in
  *scripts/validate.py*) printf 'validate-tree %s\n' "$(git ls-files | tr '\n' ' ')" >> "$FAKE_LOG"
                         echo "validate stub"; exit "${FAKE_VALIDATE_RC:-0}" ;;
esac
rc=${FAKE_GATE_RC:-0}
if [ -n "${FAKE_GATE_SEQ:-}" ]; then
  codes=($FAKE_GATE_SEQ); n=$(cat "$FAKE_LOG.gate" 2>/dev/null || echo 0); echo $((n + 1)) > "$FAKE_LOG.gate"
  rc=${codes[$(( n < ${#codes[@]} ? n : ${#codes[@]} - 1 ))]}
fi
echo "${FAKE_GATE_LINE:-Codex review finished at 2026-10-10T00:00:00Z after the latest trigger 2026-10-09T00:00:00Z}"
exit "$rc"
'''
FAKE_SLEEP = "#!/bin/sh\nexit 0\n"


def git(repo, *args):
    environment = {**tests.hermetic_git_environment(), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=environment)
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr.strip()[:300]}")
    return done.stdout.strip()


# ---------------------------------------------------------------------------------------------- the scripts' decision text
class Script:
    """One landing script, with its decision sites cut out by start and end lines (the correction #136 harness's regexes)."""

    def __init__(self, key):
        self.key = key
        self.path = LANDING / f"{key}_land.sh"
        self.text = self.path.read_text(encoding="utf-8")
        self.lines = self.text.split("\n")
        self.tcc = self.cut(r"^tcc_read_gate\(\) \{$", r"^\}$")
        self.verdict_loop = self.cut(r"^for v in (\$\{VERDICT_FILES:-\}|\"\$@\"); do$", r"^done$")
        self.gpt = self.cut(r'^if \[ "\$\{CODEX_STATE:-0\}" = 5 \]; then$', r"^fi$") if key == "uet" else None
        self.change = self.cut(r"^change\(\) \{", r"^same_change\(\) \{")
        if key == "uet":
            self.ci = self.cut(r'^  s=\$\(lg_ci_state "\$N"\)$', r'^  s=\$\(lg_ci_state "\$N"\)$')
        else:
            self.ci = self.cut(r'^  c=\$\(gh api "repos/\$R/commits/\$hd/check-runs', r"@tsv'\)$")
        found = re.findall(r"^# >>> land-gate-fns$.*?^# <<< land-gate-fns$", self.text, re.S | re.M)
        if len(found) != 1:
            raise AssertionError(f"{key}_land.sh needs exactly one land-gate-fns block, it has {len(found)}")
        self.block = found[0]
        self.git_line = self.cut(r"^LG_GIT=", r"^LG_GIT=")  # how the block is told which repository to use

    def cut(self, start_re, end_re):
        start = next((i for i, line in enumerate(self.lines) if re.search(start_re, line)), None)
        if start is None:
            raise AssertionError(f"{self.key}_land.sh: no line matches {start_re}")
        end = next((i for i in range(start, len(self.lines)) if re.search(end_re, self.lines[i])), None)
        if end is None:
            raise AssertionError(f"{self.key}_land.sh: no end line matches {end_re}")
        return "\n".join(self.lines[start:end + 1])

    def line(self, prefix):
        found = [line for line in self.lines if line.startswith(prefix)]
        if len(found) != 1:
            raise AssertionError(f"{self.key}_land.sh: {len(found)} lines start with {prefix!r}")
        return found[0]


class LandingCase(unittest.TestCase):
    """A scratch directory, the fake commands on PATH, and a bash runner for the extracted text."""

    @classmethod
    def setUpClass(cls):
        scratch = tempfile.TemporaryDirectory(prefix="landing-")
        cls.addClassCleanup(scratch.cleanup)
        cls.dir = Path(scratch.name)
        cls.bin = cls.dir / "bin"
        cls.bin.mkdir()
        for name, text in (("gh", FAKE_GH), ("python3", FAKE_PYTHON3), ("sleep", FAKE_SLEEP)):
            (cls.bin / name).write_text(text, encoding="utf-8")
            (cls.bin / name).chmod(0o755)
        cls.uet, cls.nas = Script("uet"), Script("nas")
        cls.counter = itertools.count(1)

    def env(self, **extra):
        env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "HOME": "/home/example", "LC_ALL": "C.UTF-8",
               **tests.HERMETIC_GIT_ENVIRONMENT}
        env.update(extra)
        return env

    def bash(self, prelude, body, **extra):
        done = subprocess.run(["bash", "-c", f"set -u\n{prelude}\n{body}\n"], capture_output=True, text=True,
                              env=self.env(**extra), timeout=60)
        return done.returncode, (done.stdout + done.stderr).strip()

    def write(self, name, content):
        path = self.dir / f"{next(self.counter)}-{name}"
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return path

    # -- the sites
    def verdict_files(self, script, path, head, gates_done=None):
        gates = f"GATES_DONE={q(gates_done)}" if gates_done else "unset GATES_DONE"
        prelude = f"R=x/y; N=1; E={head}; EF={head}\n{gates}\n{script.block}\n"
        prelude += f"VERDICT_FILES={q(path)}\n" if script.key == "uet" else f"set -- {q(path)}\n"
        return self.bash(prelude, script.verdict_loop)

    def gpt_block(self, path, head):
        prelude = f"R=x/y; N=1; E={head}; CODEX_STATE=5; GPT_VERDICT={q(path)}\n{self.uet.block}\n"
        return self.bash(prelude, self.uet.gpt)

    def record_gate(self, script, head, coord, statuses):
        feed = self.write("statuses.json", json.dumps(statuses))
        prelude = f"R=x/y; N=1; E={head}\nCOORD={q(coord)}\nexport FAKE_STATUSES={q(feed)}\n{script.block}\n{script.tcc}\n"
        return self.bash(prelude, 'tcc_read_gate "$E"')

    def change_prelude(self, script, repo):
        if script.key == "uet":
            return f"U={repo}\n{script.git_line}\n{script.block}\n"
        return f'G="git -C {repo}"\n{script.git_line}\n{script.block}\n'

    def change_same(self, script, repo, a, b):
        return self.bash(self.change_prelude(script, repo), f"{script.change}\nsame_change {a} {b}")

    def change_id(self, script, repo, commit):
        return self.bash(self.change_prelude(script, repo), f"lg_change_id {commit}")

    def ci_line(self, script, document):
        feed = self.write("ci.json", json.dumps(document))
        if script.key == "uet":
            return self.bash(f"R=x/y; N=1\nexport FAKE_PRVIEW={q(feed)}\n{script.block}\n", f'{script.ci}\necho "$s"')
        return self.bash(f"R=x/y; N=1; hd=abc\nexport FAKE_CHECKRUNS={q(feed)}\n", f'{script.ci}\necho "$c"')


def accept(code, reject_code=2):
    return "accept" if code == 0 else "reject" if code == reject_code else f"error:rc{code}"


# ---------------------------------------------------------------------------------------------- 1. the script text
class ScriptTextTests(LandingCase):
    def test_no_home_literal_or_user_name_in_tools_landing(self):
        pattern = re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]|[A-Za-z]:[\\/]+Users[\\/]|/root/")
        for path in sorted(LANDING.iterdir()):
            with self.subTest(file=path.name):
                self.assertEqual(pattern.findall(path.read_text(encoding="utf-8")), [])

    def test_scripts_parse_and_have_the_expected_modes(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                done = subprocess.run(["bash", "-n", str(script.path)], capture_output=True, text=True)
                self.assertEqual((done.returncode, done.stderr), (0, ""))
                self.assertTrue(script.path.stat().st_mode & stat.S_IXUSR, "the shell scripts are run by path")
                self.assertTrue(script.text.startswith("#!/usr/bin/env bash\n"))
        source = (LANDING / "codex_gate.py").read_text(encoding="utf-8")
        compile(source, "codex_gate.py", "exec")

    def test_body_runs_inside_one_group_parsed_before_it_runs(self):
        # "Parsed whole before it runs: an edit while a landing runs cannot shift what the running copy executes" (2026-10-09).
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                lines = script.lines
                self.assertEqual(lines[lines.index("set -u") + 2], "{", "the group opens after set -u and its comment")
                self.assertEqual([line for line in lines if line][-1], "}")
                self.assertEqual(sum(1 for line in lines if line == "{"), 1)

    def test_shared_block_is_identical_in_both_scripts_apart_from_the_ci_function(self):
        marker = "# The CI state of a pull request as one tab-separated line"
        self.assertEqual(self.uet.block.count(marker), 1)
        self.assertNotIn("lg_ci_state", self.nas.block)
        uet_without_ci = self.uet.block[:self.uet.block.index(marker)] + "# <<< land-gate-fns"
        self.assertEqual(uet_without_ci, self.nas.block)

    def test_scripts_run_the_gate_isolated_and_through_the_variable(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                self.assertEqual(script.text.count('python3 -I "$GATE" "$R" "$N"'), 2, "before the wait and before the merge")
                self.assertEqual(len(re.findall(r"^GATE=", script.text, re.M)), 1)

    def test_readme_names_every_variable_and_exit_code_the_scripts_use(self):
        readme = (LANDING / "README.md").read_text(encoding="utf-8")
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                for name in sorted(set(re.findall(r"\bLANDING_[A-Z_]+\b", script.text))):
                    self.assertIn(f"`{name}`", readme)
                for name in ("VERDICT_FILES", "GATES_DONE", "GPT_VERDICT"):
                    if name in script.text:
                        self.assertIn(f"`{name}`", readme)
                section = readme.split("## Exit codes", 1)[1].split("\n## ", 1)[0]
                codes = sorted(set(re.findall(r"\bexit (\d+)\b", script.text)) - {"0", "1"}, key=int)
                self.assertTrue(codes)
                for code in codes:
                    self.assertRegex(section, rf"(?<![0-9]){code} [A-Za-z]", f"exit {code} is not described")

    def evaluate(self, lines, names, arg0="landing.sh", **extra):
        script = "set -u\n" + "\n".join(lines) + "\n" + "".join(f'printf "%s\\n" "${name}"\n' for name in names)
        done = subprocess.run(["bash", "-c", script, arg0], capture_output=True, text=True, env=self.env(**extra), timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.split("\n")[:len(names)]

    def test_variables_default_to_the_documented_paths_and_can_be_overridden(self):
        uet = [self.uet.line("U=")]
        nas_g = self.nas.line("G=")
        base = {"HOME": "/home/example"}
        state = "/home/example/.local/state/native-agent-stack/coordination"
        cases = [
            ("defaults", {}, ["/home/example/code/us-equities-trading", state]),
            ("XDG_STATE_HOME", {"XDG_STATE_HOME": "/xdg"}, ["/home/example/code/us-equities-trading", "/xdg/native-agent-stack/coordination"]),
            ("LANDING_COORD wins over XDG", {"XDG_STATE_HOME": "/xdg", "LANDING_COORD": "/c"}, ["/home/example/code/us-equities-trading", "/c"]),
            ("LANDING_UET_REPO", {"LANDING_UET_REPO": "/r"}, ["/r", state]),
            ("empty overrides fall back", {"LANDING_UET_REPO": "", "LANDING_COORD": ""}, ["/home/example/code/us-equities-trading", state]),
        ]
        for name, extra, expected in cases:
            with self.subTest(script="uet", case=name):
                self.assertEqual(self.evaluate(uet, ["U", "COORD"], **{**base, **extra}), expected)
        nas_cases = [
            ("defaults", {}, ["git -C /home/example/code/native-agent-stack", state]),
            ("LANDING_NAS_REPO", {"LANDING_NAS_REPO": "/n"}, ["git -C /n", state]),
            ("LANDING_COORD", {"LANDING_COORD": "/c"}, ["git -C /home/example/code/native-agent-stack", "/c"]),
            ("XDG_STATE_HOME", {"XDG_STATE_HOME": "/xdg"}, ["git -C /home/example/code/native-agent-stack", "/xdg/native-agent-stack/coordination"]),
            ("empty overrides fall back", {"LANDING_NAS_REPO": "", "LANDING_COORD": ""}, ["git -C /home/example/code/native-agent-stack", state]),
        ]
        for name, extra, expected in nas_cases:
            with self.subTest(script="nas", case=name):
                self.assertEqual(self.evaluate([nas_g], ["G", "COORD"], **{**base, **extra}), expected)

    def test_gate_defaults_to_the_directory_of_the_script_with_symlinks_resolved(self):
        gate_line = self.uet.line("GATE=")
        self.assertEqual(gate_line, self.nas.line("GATE="), "both scripts compute the gate path the same way")
        link_dir = self.dir / f"links-{next(self.counter)}"
        link_dir.mkdir()
        (link_dir / "land").symlink_to(self.uet.path)
        real = os.path.realpath(LANDING)
        cases = [("direct", str(self.uet.path), {}, f"{real}/codex_gate.py"),
                 ("through a symlink", str(link_dir / "land"), {}, f"{real}/codex_gate.py"),
                 ("LANDING_GATE", str(link_dir / "land"), {"LANDING_GATE": "/g/gate.py"}, "/g/gate.py")]
        for name, arg0, extra, expected in cases:
            with self.subTest(case=name):
                self.assertEqual(self.evaluate([gate_line], ["GATE"], arg0=arg0, **extra), [expected])


# ---------------------------------------------------------------------------------------------- 2. verdict files
def synthetic_verdict_files():
    h, w = HEAD, OTHER
    u = "seathatflowsinourveins/us-equities-trading#44"
    return {
        "astra-ack": (f"# GPT verdict on PR {u} at {h}: ACK\n\nbody\n", "accept"),
        "astra-pass-dash": (f"# GPT verdict on PR {u} at {h}: PASS — with notes\n", "accept"),
        "astra-ack-link": (f"# GPT verdict on PR {u} at {h}: ACK — [Codex limit reply 6097595105](https://example.invalid/x)\n", "accept"),
        "astra-ack-crlf": (f"# GPT verdict on PR {u} at {h}: ACK\r\n\r\nbody\r\n", "accept"),
        "astra-cr": (f"# GPT verdict on PR {u} at {h}: CHANGES_REQUESTED\n\nthe reader says ACK elsewhere and PASS here\n", "reject"),
        "astra-cr-with-ack-line": (f"# GPT verdict on PR {u} at {h}: CHANGES_REQUESTED\n\n{h[:8]} ACK\n", "reject"),
        "astra-ack-after": (f"# GPT verdict on PR {u} at {h}: ACK_AFTER\n", "reject"),
        "astra-ackish-word": (f"# GPT verdict on PR {u} at {h}: ACKNOWLEDGED\n", "reject"),
        "astra-bypass": (f"# GPT verdict on PR {u} at {h}: BYPASS\n", "reject"),
        "astra-wrong-head": (f"# GPT verdict on PR {u} at {w}: ACK\n\nmentions {h[:8]} here\n", "reject"),
        "head-only-in-body": (f"# notes\n\nACK at {h[:8]}\n", "reject"),
        "head-inside-longer-hex": (f"# GPT verdict on PR {u} at 00{h}: ACK\n", "reject"),
        "ack-anywhere-no-head-line1": (f"# verdict\n\n{h[:8]} was read; PASS\n", "reject"),
        "empty": ("", "reject"),
        "gate-line": (f"# Read of PR {u}\n\nGate line: PASS at {h[:8]}\n", "accept"),
        "gate-line-note": (f"# Read\n\nGate line: PASS at {h[:8]} (P3s non-blocking; landing still needs the rebase).\n", "accept"),
        "verdict-co-op-40hex": (f"# Adjudication\n\nVerdict: PASS at {h} (co-op ns2604-coop, 2026-10-10).\n", "accept"),
        "verdict-by-closure": (f"# Closure\n\nVerdict: ACK (by closure) at {h}.\n", "accept"),
        "verdict-cr": (f"# Read\n\nVerdict: CHANGES_REQUESTED at {h[:8]}\n", "reject"),
        "gate-line-cr-after-ack-title": (f"# GPT verdict on PR {u} at {h}: ACK\n\nVerdict: CHANGES_REQUESTED at {h[:8]} after the rebase\n", "reject"),
        "gate-line-then-cr-later": (f"# Read\n\nGate line: PASS at {h[:8]}\n\nVerdict: CHANGES_REQUESTED at {h[:8]}\n", "reject"),
        "cr-then-gate-line-later": (f"# Read\n\nVerdict: CHANGES_REQUESTED at {h[:8]}\n\nGate line: PASS at {h[:8]}\n", "accept"),
        "title-cr-then-gate-line": (f"# GPT verdict on PR {u} at {h}: CHANGES_REQUESTED\n\nGate line: PASS at {h[:8]}\n", "reject"),
        "gate-line-other-head": (f"# Read\n\nGate line: PASS at {w[:8]}\n\nmentions {h[:8]} in prose, PASS\n", "reject"),
        "gate-line-lowercase-pass": (f"# Read\n\nGate line: pass at {h[:8]}\n", "reject"),
        "gate-line-word-between": (f"# Read\n\nGate line: PASS maybe at {h[:8]}\n", "reject"),
        "verdict-pointer": (f"# Handoff\n\nVerdict: coordination/cc-reads-{h[:8]}/pr1/GPT-VERDICT-{h[:8]}.md (read it in full)\n", "reject"),
        "brief-template": (f"# Brief for {h[:8]}\n\nVERDICT: ACK when items 1-7 hold, else CHANGES_REQUESTED with P-levels.\n", "reject"),
    }


def extra_verdict_files():
    """Beyond the harness's 28: one case for each guard of lg_last_verdict and lg_verdict_file_ok that none of them reached."""
    h = HEAD
    return {
        "gate-line-pass-with-p3": (f"# Read\n\nGate line: PASS_WITH_P3 at {h[:8]}\n", "accept"),
        "gate-line-quoted-in-prose": (f"# Read\n\nThe template says \"Gate line: PASS at {h[:8]}\" and this file has no such line.\n", "reject"),
        "record-style-line-in-a-verdict-file": (f"# Notes\n\n- Verdict at {h[:8]}: PASS\n", "reject"),
        "cr-word-only-on-line-two": (f"# GPT verdict on PR x#44 at {h}: ACK\nThe previous round was CHANGES_REQUESTED.\n", "accept"),
        "another-colon-between-head-and-word": (f"# GPT verdict on PR x#44 at {h}: note: ACK\n", "reject"),
        "gate-line-then-record-style-line": (f"# Read\n\nGate line: PASS at {h[:8]}\n\n- Verdict at {h[:8]}: CHANGES_REQUESTED\n", "accept"),
    }


class VerdictFileTests(LandingCase):
    def test_synthetic_verdict_files_through_both_loops_and_the_gpt_block(self):
        cases = synthetic_verdict_files()
        self.assertEqual(len(cases), 28)
        self.assertEqual(len(extra_verdict_files()), 6)
        for name, (content, expected) in {**cases, **extra_verdict_files()}.items():
            path = self.write(f"{name}.md", content)
            for script in (self.uet, self.nas):
                with self.subTest(file=name, site=f"{script.key}.verdict_files"):
                    self.assertEqual(accept(self.verdict_files(script, path, HEAD)[0]), expected)
            with self.subTest(file=name, site="uet.gpt_verdict"):
                self.assertEqual(accept(self.gpt_block(path, HEAD)[0], 9), expected)

    def test_an_accepted_file_is_rejected_for_another_head(self):
        for name, (content, expected) in {**synthetic_verdict_files(), **extra_verdict_files()}.items():
            if expected != "accept":
                continue
            path = self.write(f"{name}.md", content)
            for script in (self.uet, self.nas):
                with self.subTest(file=name, site=script.key):
                    self.assertEqual(accept(self.verdict_files(script, path, "1234abcd" + "0" * 32)[0]), "reject")
            with self.subTest(file=name, site="uet.gpt_verdict"):
                self.assertEqual(accept(self.gpt_block(path, "1234abcd" + "0" * 32)[0], 9), "reject")

    def test_head_prefix_must_be_eight_lower_case_hex_characters(self):
        path = self.write("ack.md", f"# GPT verdict on PR x#1 at {HEAD}: ACK\n")
        for script in (self.uet, self.nas):
            for prefix in ("3d8c634", "3D8C6344", "3d8c634g", "3d8c63444"):
                with self.subTest(site=script.key, prefix=prefix):
                    prelude = f"R=x/y; N=1\n{script.block}\n"
                    code, out = self.bash(prelude, f'lg_verdict_file_ok {q(path)} {prefix}')
                    self.assertEqual(code, 1, out)
                    self.assertIn("not 8 lower-case hex", out)

    def test_a_missing_file_is_rejected_with_its_reason(self):
        absent = self.dir / "absent.md"
        for script in (self.uet, self.nas):
            with self.subTest(site=script.key, where="the loop"):
                code, out = self.verdict_files(script, absent, HEAD)
                self.assertEqual(code, 2)
                self.assertIn("verdict file missing", out)
            with self.subTest(site=script.key, where="lg_verdict_file_ok"):
                code, out = self.bash(f"R=x/y; N=1\n{script.block}\n", f"lg_verdict_file_ok {q(absent)} {HEAD[:8]}")
                self.assertEqual((code, out), (1, "file missing"))

    def test_landing_gate_rule_needs_a_receipt_naming_the_head(self):
        phrases = ("The path to PASS is the rebase.", "This is a landing gate.", "Do this before landing.",
                   "A landing condition applies.", "THE PATH TO PASS IS HERE")
        receipt = self.write("receipt.txt", f"gates done at {HEAD[:8]}\n")
        wrong = self.write("wrong-receipt.txt", f"gates done at {OTHER[:8]}\n")
        near = self.write("near-receipt.txt", f"gates done at {HEAD[:7]}g\n")  # seven of the eight characters
        for phrase in phrases:
            path = self.write("gate.md", f"# GPT verdict on PR x#44 at {HEAD}: ACK\n\n{phrase}\n")
            for script in (self.uet, self.nas):
                with self.subTest(site=script.key, phrase=phrase):
                    self.assertEqual(self.verdict_files(script, path, HEAD)[0], 2)
                    self.assertEqual(self.verdict_files(script, path, HEAD, gates_done=wrong)[0], 2)
                    self.assertEqual(self.verdict_files(script, path, HEAD, gates_done=near)[0], 2)
                    self.assertEqual(self.verdict_files(script, path, HEAD, gates_done=self.dir / "absent.txt")[0], 2)
                    self.assertEqual(self.verdict_files(script, path, HEAD, gates_done=receipt)[0], 0)
        plain = self.write("plain.md", f"# GPT verdict on PR x#44 at {HEAD}: ACK\n\nnothing about gates\n")
        for script in (self.uet, self.nas):
            with self.subTest(site=script.key, phrase="none"):
                self.assertEqual(self.verdict_files(script, plain, HEAD)[0], 0)


# ---------------------------------------------------------------------------------------------- 3. the trading-cc-read gate
def synthetic_records():
    h, o = "aabbccdd11223344556677889900aabbccddeeff", "11223344ffeeddccbbaa00998877665544332211"
    return h, {
        "last-verdict-pass": (f"# r\n\n- **Verdict at `{o[:8]}`: CHANGES_REQUESTED**\n\n- **Verdict at `{h[:8]}`: PASS at micro scope**\n", "accept"),
        "last-verdict-cr-earlier-pass": (f"# r\n\n- **Verdict at `{h[:8]}`: PASS**\n\nlater: **Verdict at `{h[:8]}`: CHANGES_REQUESTED** (Astra)\n", "reject"),
        "pass-belongs-to-another-head": (f"# r\n\n- **Verdict at `{o[:8]}`: PASS**\n\n- Verdict at {h[:8]}: CHANGES_REQUESTED\n", "reject"),
        "head-only-in-prose": (f"# r\n\n{h[:8]} was read and everything passed: PASS\n", "reject"),
        "heading-then-next-line": (f"# r\n\n### Verdict at `{h[:8]}`\nPASS at micro scope\n", "reject"),
        "gate-line-last": (f"# r\n\n### Verdict at `{h[:8]}`\nCHANGES_REQUESTED\n\nGate line: PASS at {h[:8]}\n", "accept"),
        "gate-line-before-cr": (f"# r\n\nGate line: PASS at {h[:8]}\n\n**Verdict at {h[:8]}: CHANGES_REQUESTED**\n", "reject"),
        "both-words-one-line": (f"# r\n\n**Verdict at {h[:8]}: CHANGES_REQUESTED, my PASS is withdrawn**\n", "reject"),
        "ack-verdict": (f"# r\n\nVerdict: ACK at {h[:8]}\n", "accept"),
        "no-verdict-line": (f"# r\n\nread {h[:8]}; all good, PASS\n", "reject"),
        "upper-verdict": (f"# r\n\nVERDICT {h[:8]}: PASS\n", "accept"),
        "empty": ("", "reject"),
        "head-inside-longer-hex": (f"# r\n\n**Verdict at 00{h[:8]}: PASS**\n", "reject"),
        "head-after-the-first-colon": (f"# r\n\nVerdict: the read of {h[:8]}: PASS\n", "reject"),
        "verdict-inside-a-word": (f"# r\n\nMyverdict at {h[:8]}: PASS\n", "reject"),
        "another-colon-between-head-and-word": (f"# r\n\nVerdict at {h[:8]}: note: PASS\n", "reject"),
        "decorated-word": (f"# r\n\n- Verdict at {h[:8]}: **PASS**\n", "accept"),
    }


class TccReadGateTests(LandingCase):
    def status(self, state, description, updated="2026-10-10T00:00:00Z", context="trading-cc-read"):
        return {"context": context, "state": state, "description": description, "updated_at": updated}

    def test_the_synthetic_records_decide_by_their_last_verdict_line(self):
        head, records = synthetic_records()
        self.assertEqual(len(records), 17, "the harness's 12 and five more")
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        reasons = {"no-verdict-line": "no Verdict/Gate line gives a verdict for aabbccdd",
                   "last-verdict-cr-earlier-pass": "the last verdict line for aabbccdd is CHANGES_REQUESTED"}
        for name, (content, expected) in records.items():
            (coord / f"trading-cc/reads/{name}.md").write_text(content, encoding="utf-8")
            for script in (self.uet, self.nas):
                with self.subTest(record=name, site=script.key):
                    status = [self.status("success", f"PASS: trading-cc/reads/{name}.md")]
                    code, out = self.record_gate(script, head, coord, status)
                    self.assertEqual(accept(code), expected, out)
                    if name in reasons:
                        self.assertIn(reasons[name], out)

    def test_description_forms(self):
        head = "aabbccdd11223344556677889900aabbccddeeff"
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        for relative in ("trading-cc/reads/x.md", "trading-cc/reads/xamd", "trading-cc/reads/x.txt", "trading-cc/x.md"):
            (coord / relative).write_text("# r\n\nVerdict at aabbccdd: PASS\n", encoding="utf-8")
        forms = [("PASS: trading-cc/reads/x.md", "accept"), ("ACK: trading-cc/reads/x.md", "accept"),
                 ("CHANGES_REQUESTED: trading-cc/reads/x.md", "reject"), ("PASS (micro) pending: trading-cc/reads/x.md", "reject"),
                 ("PASSED: trading-cc/reads/x.md", "reject"), ("FAIL: trading-cc/reads/x.md", "reject"),
                 ("PASS: trading-cc/reads/x.txt", "reject"), ("PASS: trading-cc/reads/../x.md", "reject"),
                 ("PASS: trading-cc/reads/x.md and more", "reject"), ("pass: trading-cc/reads/x.md", "reject"),
                 ("xPASS: trading-cc/reads/x.md", "reject"), ("PASS: trading-cc/reads/xamd", "reject"),
                 ("PASS: trading-cc/reads/x.md\nmore", "reject"), ("PASS:  trading-cc/reads/x.md", "reject")]
        for description, expected in forms:
            for script in (self.uet, self.nas):
                with self.subTest(description=description, site=script.key):
                    code = self.record_gate(script, head, coord, [self.status("success", description)])[0]
                    self.assertEqual(accept(code), expected)

    def test_failure_pending_and_other_states_stop_and_no_status_is_no_gate(self):
        head, records = synthetic_records()
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        (coord / "trading-cc/reads/good.md").write_text(records["ack-verdict"][0], encoding="utf-8")
        good = "PASS: trading-cc/reads/good.md"
        cases = [("failure with a good description", [self.status("failure", good)], 2),
                 ("pending", [self.status("pending", good)], 2),
                 ("error", [self.status("error", good)], 2),
                 ("no status at all", [], 0),
                 ("another context failing is not this gate", [self.status("failure", good, context="other")], 0),
                 ("newer success replaces an older failure", [self.status("failure", good, "2026-10-10T00:00:00Z"),
                                                              self.status("success", good, "2026-10-10T01:00:00Z")], 0),
                 ("newer failure replaces an older success", [self.status("success", good, "2026-10-10T00:00:00Z"),
                                                              self.status("failure", good, "2026-10-10T01:00:00Z")], 2)]
        for name, statuses, expected in cases:
            for script in (self.uet, self.nas):
                with self.subTest(case=name, site=script.key):
                    self.assertEqual(self.record_gate(script, head, coord, statuses)[0], expected)

    def test_a_head_that_is_not_hexadecimal_is_refused_with_its_reason(self):
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        (coord / "trading-cc/reads/x.md").write_text("# r\n\nVerdict: PASS at GGGGGGGG\n", encoding="utf-8")
        for script in (self.uet, self.nas):
            with self.subTest(site=script.key):
                code, out = self.record_gate(script, "G" * 40, coord, [self.status("success", "PASS: trading-cc/reads/x.md")])
                self.assertEqual(code, 2)
                self.assertIn("not 8 lower-case hex", out)

    def test_a_missing_record_is_rejected(self):
        head = "aabbccdd11223344556677889900aabbccddeeff"
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        for script in (self.uet, self.nas):
            with self.subTest(site=script.key):
                code, out = self.record_gate(script, head, coord, [self.status("success", "PASS: trading-cc/reads/none.md")])
                self.assertEqual(code, 2)
                self.assertIn("record missing", out)


# ---------------------------------------------------------------------------------------------- 4. change identity
class ChangeIdentityTests(LandingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.repo, cls.refs = cls.build_repo(cls.dir)

    @staticmethod
    def build_repo(tmp):
        repo = Path(tmp) / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        (repo / "manifests").mkdir()
        (repo / "a.txt").write_text("line one\nline two\n")
        (repo / "run.sh").write_text("#!/bin/sh\necho hi\n")
        (repo / "blob.bin").write_bytes(bytes(64))
        (repo / "dash.txt").write_text("alpha\n-- gone\nomega\n")
        (repo / "naïve file.txt").write_text("x\n")
        (repo / "sp ace.txt").write_text("s\n")
        (repo / "ctx.txt").write_text("".join(f"c{i}\n" for i in range(1, 11)))
        (repo / "manifests/evidence.json").write_text('{"rows": 1}\n')
        (repo / "target.txt").write_text("t\n")
        os.symlink("target.txt", repo / "link")

        def commit_all(message):
            git(repo, "add", "-A", "--", ".")
            git(repo, "commit", "-q", "--allow-empty", "-m", message)
            return git(repo, "rev-parse", "HEAD")

        base = commit_all("base")
        git(repo, "update-ref", "refs/remotes/origin/main", base)
        refs = {"base": base}

        def branch(name, start, edit, message):
            git(repo, "checkout", "-q", "-f", "-B", name, start)
            edit()
            refs[name] = commit_all(message)

        def read_edit():
            (repo / "a.txt").write_text("line one\nline two\nline three\n")
            (repo / "run.sh").write_text("#!/bin/sh\necho hi\necho more\n")
            (repo / "blob.bin").write_bytes(bytes([1]) * 64)
            (repo / "dash.txt").write_text("alpha\n-- gone\nomega\nextra\n")
            (repo / "naïve file.txt").write_text("x\ny\n")
            (repo / "sp ace.txt").write_text("s\nt\n")
            (repo / "ctx.txt").write_text("".join(f"c{i}\n" if i != 5 else "c5 edited\n" for i in range(1, 11)))
            (repo / "manifests/evidence.json").write_text('{"rows": 2}\n')

        branch("read", "main", read_edit, "read head")
        branch("same-again", "read", lambda: None, "same content, new commit")
        branch("v-ordinary", "read", lambda: (repo / "a.txt").write_text("line one\nline two\nline three\nline four\n"), "ordinary line")
        branch("v-binary", "read", lambda: (repo / "blob.bin").write_bytes(bytes([2]) * 64), "other bytes of a binary file")
        branch("v-execbit", "read", lambda: os.chmod(repo / "a.txt", 0o755), "executable bit")
        branch("v-space-name", "read", lambda: (repo / "sp ace.txt").write_text("s\nu\n"), "text change in a file name with a space")
        branch("v-nonascii-name", "read", lambda: (repo / "naïve file.txt").write_text("x\nz\n"), "text change in a non-ASCII file name")
        branch("v-removed-dashdash", "read", lambda: (repo / "dash.txt").write_text("alpha\nomega\nextra\n"), "removed base line starting --")
        branch("v-added-plusplus", "read", lambda: (repo / "a.txt").write_text("line one\nline two\nline three\n++ tampered\n"), "added line starting ++")
        branch("v-trailing-space", "read", lambda: (repo / "a.txt").write_text("line one\nline two\nline three \n"), "trailing space on an added line")
        branch("v-extra-file", "read", lambda: (repo / "new.txt").write_text("n\n"), "extra file")
        branch("v-evidence-only", "read", lambda: (repo / "manifests/evidence.json").write_text('{"rows": 3}\n'), "evidence.json differs only")
        branch("v-symlink", "read", lambda: (os.remove(repo / "link"), os.symlink("run.sh", repo / "link")), "retargeted symlink")
        branch("v-moved-line", "read", lambda: (repo / "a.txt").write_text("line three\nline one\nline two\n"), "same added line at another position")
        branch("v-copy", "read", lambda: ((repo / "a.txt").write_text("line one\nline two\nline three\nline four\n"),
                                          (repo / "a-copy.txt").write_text("line one\nline two\nline three\n")), "a copy of a modified file")
        # a main that moved: an edit two lines away from the PR's edit of ctx.txt, and a new file
        branch("main2", "main", lambda: ((repo / "ctx.txt").write_text("".join(f"c{i}\n" if i != 2 else "c2 main\n" for i in range(1, 11))),
                                         (repo / "extra-main.txt").write_text("m\n")), "main moves")
        git(repo, "checkout", "-q", "-f", "-B", "rebased", "main2")
        git(repo, "cherry-pick", refs["read"])
        refs["rebased"] = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "-f", "-B", "merged", "read")
        git(repo, "merge", "-q", "--no-ff", "-m", "merge main2", "main2")
        refs["merged"] = git(repo, "rev-parse", "HEAD")
        return repo, refs

    def cases(self):
        r = self.refs
        return [
            ("identical head", r["read"], r["read"], "same", "base"),
            ("same content in a new commit", r["read"], r["same-again"], "same", "base"),
            ("pure rebase onto a main that moved (hunk context shifts)", r["read"], r["rebased"], "same", "main2"),
            ("merge-update with the moved main", r["read"], r["merged"], "same", "main2"),
            ("control: an ordinary added line", r["read"], r["v-ordinary"], "differ", "base"),
            ("control: a retargeted symlink", r["read"], r["v-symlink"], "differ", "base"),
            ("control: an extra file", r["read"], r["v-extra-file"], "differ", "base"),
            ("blind spot: other bytes of a binary file the PR already edits", r["read"], r["v-binary"], "differ", "base"),
            ("blind spot: only the executable bit of a file the PR already edits", r["read"], r["v-execbit"], "differ", "base"),
            ("blind spot: text change in a file name with a space", r["read"], r["v-space-name"], "differ", "base"),
            ("blind spot: text change in a non-ASCII file name", r["read"], r["v-nonascii-name"], "differ", "base"),
            ("blind spot: a removed base line that starts with --", r["read"], r["v-removed-dashdash"], "differ", "base"),
            ("blind spot: an added line that starts with ++ at column 0", r["read"], r["v-added-plusplus"], "differ", "base"),
            ("blind spot: a trailing space on an added line", r["read"], r["v-trailing-space"], "differ", "base"),
            ("empty change on both sides is refused", r["base"], r["base"], "refuse", "base"),
            ("read head against an empty change differs", r["read"], r["base"], "differ", "base"),
            ("known limitation: the same added line at another position of the same file", r["read"], r["v-moved-line"], "same", "base"),
        ]

    def set_main(self, which):
        git(self.repo, "update-ref", "refs/remotes/origin/main", self.refs["main2"] if which == "main2" else self.refs["base"])

    def test_seventeen_scratch_repository_cases_for_both_scripts(self):
        cases = self.cases()
        self.assertEqual(len(cases), 17)
        for name, a, b, expected, main in cases:
            for script in (self.uet, self.nas):
                with self.subTest(case=name, site=script.key):
                    self.set_main(main)
                    code, out = self.change_same(script, self.repo, a, b)
                    self.assertEqual(code, 0 if expected == "same" else 1, out)

    def reference_id(self, commit, exclude=None):
        """patch-id of the neutral diff between the commit and its merge base, spelled out here with every neutralizing flag."""
        env = tests.hermetic_git_environment()
        base = git(self.repo, "merge-base", commit, "origin/main")
        command = ["git", "-C", str(self.repo), "-c", "core.quotePath=false", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false",
                   "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames", "-U0", "--binary", base, commit, "--", "."]
        if exclude:
            command.append(exclude)
        patch = subprocess.run(command, capture_output=True, env=env, check=True).stdout
        out = subprocess.run(["git", "patch-id", "--verbatim"], input=patch, capture_output=True, env=env, check=True).stdout
        return out.split()[0].decode()

    def test_identity_is_the_patch_id_of_the_neutral_diff_whatever_the_users_diff_configuration(self):
        self.set_main("base")
        config, attributes = self.repo / ".git/config", self.repo / ".git/info/attributes"
        saved = {config: config.read_bytes(), attributes: attributes.read_bytes() if attributes.exists() else None}
        try:
            for key, value in (("diff.noprefix", "true"), ("diff.mnemonicPrefix", "true"), ("color.ui", "always"),
                               ("color.diff", "always"), ("diff.external", "false"), ("diff.renames", "copies"),
                               ("diff.up.textconv", "sed -e s/line/LINE/")):
                git(self.repo, "config", key, value)
            attributes.parent.mkdir(exist_ok=True)
            attributes.write_text("a.txt diff=up\n", encoding="utf-8")
            # the configuration is effective: a plain `git diff` is no longer the neutral one
            hostile = subprocess.run(["git", "-C", str(self.repo), "diff", "--no-ext-diff", self.refs["base"], self.refs["read"], "--", "a.txt"],
                                     capture_output=True, text=True, env=tests.hermetic_git_environment())
            self.assertNotEqual(hostile.stdout.count("\x1b["), 0, hostile.stderr)
            for commit in ("read", "same-again", "v-ordinary", "v-binary", "v-nonascii-name", "v-execbit", "v-copy"):
                for script in (self.uet, self.nas):
                    with self.subTest(commit=commit, site=script.key):
                        exclude = ":!manifests/evidence.json" if script.key == "nas" else None
                        code, out = self.change_id(script, self.repo, self.refs[commit])
                        self.assertEqual((code, out), (0, self.reference_id(self.refs[commit], exclude)))
        finally:
            config.write_bytes(saved[config])
            if saved[attributes] is None:
                attributes.unlink(missing_ok=True)
            else:
                attributes.write_bytes(saved[attributes])

    def test_evidence_json_is_excluded_in_nas_only(self):
        self.set_main("base")
        read, evidence = self.refs["read"], self.refs["v-evidence-only"]
        self.assertEqual(self.change_same(self.uet, self.repo, read, evidence)[0], 1)
        self.assertEqual(self.change_same(self.nas, self.repo, read, evidence)[0], 0)

    def test_a_change_that_is_empty_only_by_exclusion_is_identified_by_its_file_names(self):
        self.set_main("base")
        repo = self.repo
        git(repo, "checkout", "-q", "-f", "-B", "only-evidence-a", "main")
        (repo / "manifests/evidence.json").write_text('{"rows": 10}\n')
        git(repo, "add", "-A", "--", ".")
        git(repo, "commit", "-q", "-m", "evidence only a")
        a = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "-f", "-B", "only-evidence-b", "main")
        (repo / "manifests/evidence.json").write_text('{"rows": 11}\n')
        git(repo, "add", "-A", "--", ".")
        git(repo, "commit", "-q", "-m", "evidence only b")
        b = git(repo, "rev-parse", "HEAD")
        # nas leaves evidence.json out, so both changes are empty: they are identified by their file names (the same file)
        self.assertEqual(self.change_same(self.nas, self.repo, a, b)[0], 0)
        self.assertEqual(self.change_same(self.uet, self.repo, a, b)[0], 1)


# ---------------------------------------------------------------------------------------------- 5. the CI line
def check_run(name, status="COMPLETED", conclusion="SUCCESS"):
    return {"__typename": "CheckRun", "name": name, "status": status, "conclusion": conclusion}


def status_context(context, state):
    return {"__typename": "StatusContext", "context": context, "state": state}


def ci_reference_uet(entries):
    """What the CI line must say: incomplete, failing, total and ci-gate successes (the rule, in Python)."""
    incomplete = failing = 0
    for entry in entries:
        kind = entry.get("__typename")
        if kind == "CheckRun":
            if entry.get("status") != "COMPLETED":
                incomplete += 1
            elif entry.get("conclusion") in ("FAILURE", "CANCELLED", "TIMED_OUT"):
                failing += 1
        elif kind == "StatusContext":
            if entry.get("state") in ("PENDING", "EXPECTED"):
                incomplete += 1
            elif entry.get("state") in ("FAILURE", "ERROR"):
                failing += 1
        else:
            incomplete += 1
    gate = sum(1 for e in entries if e.get("__typename") == "CheckRun" and e.get("name") == "ci-gate" and e.get("conclusion") == "SUCCESS")
    return incomplete, failing, len(entries), gate


def nas_run(name, started, status="completed", conclusion="success"):
    return {"name": name, "status": status, "conclusion": conclusion, "started_at": started}


def ci_reference_nas(runs):
    latest = {}
    for run in runs:
        if run["name"] not in latest or run["started_at"] > latest[run["name"]]["started_at"]:
            latest[run["name"]] = run
    kept = list(latest.values())
    incomplete = sum(1 for r in kept if r["status"] != "completed")
    failing = sum(1 for r in kept if r["status"] == "completed" and r["conclusion"] in ("failure", "cancelled", "timed_out", "action_required"))
    validated = sum(1 for r in kept if r["name"] == "validate" and r["conclusion"] == "success")
    return incomplete, failing, len(kept), validated


class CiLineTests(LandingCase):
    def test_uet_ci_state_reads_check_runs_by_status_and_commit_statuses_by_state(self):
        green = [check_run("a"), check_run("b"), check_run("ci-gate")]
        cases = [
            ("all green, no commit status", green),
            ("all green plus a SUCCESS trading-cc-read", green + [status_context("trading-cc-read", "SUCCESS")]),
            ("all green plus a PENDING status", green + [status_context("trading-cc-read", "PENDING")]),
            ("all green plus an EXPECTED status", green + [status_context("other", "EXPECTED")]),
            ("all green plus a FAILURE status", green + [status_context("other", "FAILURE")]),
            ("all green plus an ERROR status", green + [status_context("other", "ERROR")]),
            ("an incomplete CheckRun", green + [check_run("slow", "IN_PROGRESS", "")]),
            ("a failing CheckRun", green + [check_run("bad", "COMPLETED", "FAILURE")]),
            ("a cancelled and a timed-out CheckRun", green + [check_run("c", "COMPLETED", "CANCELLED"), check_run("t", "COMPLETED", "TIMED_OUT")]),
            ("a NEUTRAL and a SKIPPED CheckRun do not fail", green + [check_run("n", "COMPLETED", "NEUTRAL"), check_run("s", "COMPLETED", "SKIPPED")]),
            ("ci-gate absent", [check_run("a"), check_run("b")]),
            ("ci-gate failed", [check_run("a"), check_run("ci-gate", "COMPLETED", "FAILURE")]),
            ("a status named ci-gate is not the CheckRun", [check_run("a"), status_context("ci-gate", "SUCCESS")]),
            ("a status that also carries name and conclusion is still not the CheckRun",
             [check_run("a"), {**status_context("ci-gate", "SUCCESS"), "name": "ci-gate", "conclusion": "SUCCESS"}]),
            ("zero entries", []),
            ("an entry of an unknown type counts as running", green + [{"__typename": "Surprise", "name": "x"}]),
        ]
        for name, entries in cases:
            with self.subTest(case=name):
                head = "H" * 40
                code, out = self.ci_line(self.uet, {"headRefOid": head, "statusCheckRollup": entries, "mergeStateStatus": "CLEAN"})
                incomplete, failing, total, gate = ci_reference_uet(entries)
                self.assertEqual((code, out.replace("\t", " ")), (0, f"{head} {incomplete} {failing} {total} {gate} CLEAN"))

    def test_nas_check_run_line_judges_the_latest_run_per_name(self):
        t = "2026-10-10T10:00:00Z"
        cases = [
            ("all green", [nas_run("validate", t), nas_run("lint", t)]),
            ("superseded cancelled run does not count", [nas_run("validate", t, conclusion="cancelled"), nas_run("validate", "2026-10-10T10:05:00Z")]),
            ("latest run failed", [nas_run("validate", t), nas_run("validate", "2026-10-10T10:05:00Z", conclusion="failure")]),
            ("an incomplete check", [nas_run("validate", t), nas_run("slow", "2026-10-10T10:01:00Z", status="in_progress", conclusion="")]),
            ("validate absent", [nas_run("lint", t)]),
            ("action_required counts as failing", [nas_run("validate", t), nas_run("x", t, conclusion="action_required")]),
            ("a latest cancelled run counts as failing", [nas_run("validate", t), nas_run("x", t, conclusion="cancelled")]),
            ("a latest timed_out run counts as failing", [nas_run("validate", t), nas_run("x", t, conclusion="timed_out")]),
        ]
        for name, runs in cases:
            with self.subTest(case=name):
                code, out = self.ci_line(self.nas, {"check_runs": runs})
                incomplete, failing, total, validated = ci_reference_nas(runs)
                self.assertEqual((code, out.replace("\t", " ")), (0, f"{incomplete} {failing} {total} {validated}"))


# ---------------------------------------------------------------------------------------------- 6. codex_gate.py
BOT = "chatgpt-codex-connector[bot]"
CREATED = "2026-10-10T12:00:00Z"


def comment(login, when, body=""):
    return {"user": {"login": login}, "created_at": when, "body": body}


def summary(*rows):
    return comment(BOT, "2026-10-10T12:00:30Z", "<!-- codex-pull-request-review-summary -->\n| # | Status |\n| --- | --- |\n" + "\n".join(rows))


def row(status, when):
    return f'| 1 | **{status}** <relative-time datetime="{when}">at {when}</relative-time> |'


def pending_review():
    return {"user": {"login": BOT}, "submitted_at": None}


def limit_notice(when):
    return comment(BOT, when, "You have reached your Codex usage limits for code reviews. You can see your limits in the Codex usage dashboard.")


class CodexGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("landing_codex_gate", LANDING / "codex_gate.py")
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)

    def run_gate(self, comments=(), timeline=(), reviews=(), reactions=(), created=CREATED, now="2026-10-10T12:05:00Z", fail=None):
        real = self.gate.datetime
        frozen = real.fromisoformat(now.replace("Z", "+00:00"))

        class Frozen(real):
            @classmethod
            def now(cls, tz=None):
                return frozen if tz is None else frozen.astimezone(tz)

        def fake_run(cmd, capture_output=False, text=False, check=False):
            self.assertEqual(cmd[:2], ["gh", "api"], "codex_gate.py reaches GitHub only through gh api")
            if fail == "all" or (fail == "head" and "--paginate" not in cmd) or (fail == "lists" and "--paginate" in cmd):
                if check:
                    raise subprocess.CalledProcessError(1, cmd, "", "HTTP 502")
                return subprocess.CompletedProcess(cmd, 1, "", "HTTP 502")
            path = cmd[-1]
            if "--paginate" not in cmd:
                self.assertTrue(path.endswith("/pulls/7"), path)
                return subprocess.CompletedProcess(cmd, 0, json.dumps({"created_at": created}), "")
            self.assertIn("--slurp", cmd)
            lists = {"/issues/7/comments": comments, "/issues/7/timeline": timeline, "/pulls/7/reviews": reviews,
                     "/issues/7/reactions": reactions}
            key = next(k for k in lists if path.split("?")[0].endswith(k))
            return subprocess.CompletedProcess(cmd, 0, json.dumps([list(lists[key])]), "")

        out = io.StringIO()
        with mock.patch.object(self.gate.subprocess, "run", fake_run), mock.patch.object(self.gate, "datetime", Frozen), \
                contextlib.redirect_stdout(out):
            code = self.gate.main("o/r", "7")
        return code, out.getvalue().strip()

    def test_exit_code_precedence_on_canned_api_data(self):
        completed = summary(row("Completed", "2026-10-10T12:01:00Z"))
        cases = [
            # (name, kwargs, expected exit code, text the status line must contain)
            ("a Completed row after the trigger", dict(comments=[completed]), 0, "finished at 2026-10-10T12:01:00Z"),
            ("Completed at 12:01 then Cancelled at 12:02 after the same trigger: any completion evidence passes",
             dict(comments=[summary(row("Completed", "2026-10-10T12:01:00Z"), row("Cancelled", "2026-10-10T12:02:00Z"))]), 0, "finished at 2026-10-10T12:01:00Z"),
            ("a lone Cancelled row", dict(comments=[summary(row("Cancelled", "2026-10-10T12:02:00Z"))]), 4, "ended 'Cancelled'"),
            ("Completed then Running: a running row always blocks",
             dict(comments=[summary(row("Completed", "2026-10-10T12:01:00Z"), row("Running since", "2026-10-10T12:03:00Z"))]), 3, "running since 2026-10-10T12:03:00Z"),
            ("a Running row blocks even with a +1 reaction", dict(comments=[summary(row("Running since", "2026-10-10T12:03:00Z"))],
                                                                    reactions=[{"user": {"login": BOT}, "content": "+1", "created_at": "2026-10-10T12:04:00Z"}]), 3, "running"),
            ("a usage-limit notice after the trigger", dict(comments=[limit_notice("2026-10-10T12:01:00Z")]), 5, "usage-limit"),
            ("an account notice after the trigger", dict(comments=[comment(BOT, "2026-10-10T12:01:00Z", "Please create a Codex account to use reviews.")]), 5, "usage-limit or account notice"),
            ("a notice before the trigger does not count", dict(comments=[limit_notice("2026-10-10T11:00:00Z")], now="2026-10-10T12:05:00Z"), 3, "no Codex review finished"),
            ("completion evidence wins over a later notice", dict(comments=[completed, limit_notice("2026-10-10T12:02:00Z")]), 0, "finished"),
            ("no bot activity for 10 minutes", dict(now="2026-10-10T12:10:00Z"), 5, "no connector activity in 10 min"),
            ("no bot activity for 9 minutes 59 seconds", dict(now="2026-10-10T12:09:59Z"), 3, "no Codex review finished"),
            ("some bot activity (not a notice) keeps waiting past 10 minutes", dict(comments=[comment(BOT, "2026-10-10T12:02:00Z", "Looking into it.")], now="2026-10-10T12:30:00Z"), 3, "no Codex review finished"),
            ("a +1 reaction after the trigger", dict(reactions=[{"user": {"login": BOT}, "content": "+1", "created_at": "2026-10-10T12:03:00Z"}]), 0, "finished at 2026-10-10T12:03:00Z"),
            ("a +1 reaction by a person does not count", dict(reactions=[{"user": {"login": "someone"}, "content": "+1", "created_at": "2026-10-10T12:03:00Z"}]), 3, "no Codex review"),
            ("a different reaction by the bot is activity, not completion", dict(reactions=[{"user": {"login": BOT}, "content": "eyes", "created_at": "2026-10-10T12:03:00Z"}], now="2026-10-10T12:30:00Z"), 3, "no Codex review"),
            ("a connector review after the trigger", dict(reviews=[{"user": {"login": BOT}, "submitted_at": "2026-10-10T12:04:00Z"}]), 0, "finished at 2026-10-10T12:04:00Z"),
            ("a review by a person does not count", dict(reviews=[{"user": {"login": "someone"}, "submitted_at": "2026-10-10T12:04:00Z"}]), 3, "no Codex review"),
            ("the no-findings comment after the trigger", dict(comments=[comment(BOT, "2026-10-10T12:04:00Z", "Codex Review: Didn't find any major issues. Nice work!")]), 0, "finished at 2026-10-10T12:04:00Z"),
            ("a Completed row at exactly the trigger time", dict(comments=[summary(row("Completed", CREATED))]), 0, "finished"),
            ("an account notice in other capitals", dict(comments=[comment(BOT, "2026-10-10T12:01:00Z", "Create a Codex Account first.")]), 5, "usage-limit or account notice"),
            ("a bot comment without the summary marker is not a summary", dict(comments=[comment(BOT, "2026-10-10T12:01:00Z", row("Completed", "2026-10-10T12:01:00Z"))]), 3, "no Codex review"),
            ("a pending connector review (no submission time) is not a finish", dict(reviews=[pending_review()]), 3, "no Codex review"),
            ("a person quoting the no-findings sentence is not the connector", dict(comments=[comment("someone", "2026-10-10T12:04:00Z", "Didn't find any major issues, they said.")]), 3, "no Codex review"),
            ("a person quoting the usage-limit notice is not the connector", dict(comments=[comment("someone", "2026-10-10T12:01:00Z", "You have reached your Codex usage limits, says the bot.")]), 3, "no Codex review"),
            ("a person's reaction is not connector activity",
             dict(reactions=[{"user": {"login": "someone"}, "content": "eyes", "created_at": "2026-10-10T12:02:00Z"}], now="2026-10-10T12:12:00Z"), 5, "no connector activity"),
        ]
        for name, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(**kwargs)
                self.assertEqual((got, text in line), (code, True), line)

    def test_triggers(self):
        done = summary(row("Completed", "2026-10-10T12:05:00Z"))
        later = "2026-10-10T12:10:00Z"
        cases = [
            ("a push after a finished review is not a trigger",
             dict(comments=[done], timeline=[{"event": "head_ref_force_pushed", "created_at": later}, {"event": "committed", "created_at": later}]), 0, "finished"),
            ("a comment from a person asking @codex review is a trigger", dict(comments=[done, comment("someone", later, "@codex review")]), 3, f"latest trigger {later}"),
            ("@codex security review is a trigger", dict(comments=[done, comment("someone", later, "@codex security review")]), 3, f"latest trigger {later}"),
            ("a trigger comment may be indented", dict(comments=[done, comment("someone", later, "  @codex review please")]), 3, f"latest trigger {later}"),
            ("the mention in the middle of a sentence is not a trigger", dict(comments=[done, comment("someone", later, "please ask @codex review later")]), 0, "finished"),
            ("another command is not a trigger", dict(comments=[done, comment("someone", later, "@codex summarize")]), 0, "finished"),
            ("the connector's own mention is not a trigger", dict(comments=[done, comment(BOT, later, "@codex review")]), 0, "finished"),
            ("a ready_for_review event is a trigger", dict(comments=[done], timeline=[{"event": "ready_for_review", "created_at": later}]), 3, f"latest trigger {later}"),
            ("another timeline event is not", dict(comments=[done], timeline=[{"event": "labeled", "created_at": later}]), 0, "finished"),
            ("@codex reviews is not the command", dict(comments=[done, comment("someone", later, "@codex reviews are slow")]), 0, "finished"),
            ("a Cancelled row from before the latest trigger is not this review's end",
             dict(comments=[summary(row("Cancelled", "2026-10-10T12:05:00Z")), comment("someone", later, "@codex review")]), 3, f"latest trigger {later}"),
            ("a connector review from before the latest trigger does not count",
             dict(reviews=[{"user": {"login": BOT}, "submitted_at": "2026-10-10T12:05:00Z"}], comments=[comment("someone", later, "@codex review")]), 3, "no Codex review"),
            ("a +1 reaction from before the latest trigger does not count",
             dict(reactions=[{"user": {"login": BOT}, "content": "+1", "created_at": "2026-10-10T12:05:00Z"}], comments=[comment("someone", later, "@codex review")]), 3, "no Codex review"),
            ("the no-findings comment from before the latest trigger does not count",
             dict(comments=[comment(BOT, "2026-10-10T12:05:00Z", "Didn't find any major issues."), comment("someone", later, "@codex review")]), 3, "no Codex review"),
            ("connector activity from before the latest trigger does not postpone the unavailable verdict",
             dict(comments=[comment(BOT, "2026-10-10T12:01:00Z", "Looking into it."), comment("someone", "2026-10-10T12:02:00Z", "@codex review")],
                  now="2026-10-10T12:13:00Z"), 5, "no connector activity"),
            ("a reaction from before the latest trigger is not activity either",
             dict(reactions=[{"user": {"login": BOT}, "content": "eyes", "created_at": "2026-10-10T12:01:00Z"}],
                  comments=[comment("someone", "2026-10-10T12:02:00Z", "@codex review")], now="2026-10-10T12:13:00Z"), 5, "no connector activity"),
            ("a summary comment by a person is ignored", dict(comments=[comment("someone", "2026-10-10T12:05:00Z", "<!-- codex-pull-request-review-summary -->\n" + row("Completed", "2026-10-10T12:05:00Z"))],
                                                         now="2026-10-10T12:06:00Z"), 3, "no Codex review"),
        ]
        for name, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(**{"now": "2026-10-10T12:12:00Z", **kwargs})
                self.assertEqual((got, text in line), (code, True), line)

    def test_a_failing_gh_call_is_an_error_not_a_verdict(self):
        for fail in ("all", "head", "lists"):
            with self.subTest(failing=fail), self.assertRaises(subprocess.CalledProcessError):
                self.run_gate(fail=fail)

    def test_command_line_needs_exactly_two_arguments(self):
        for argv in ([], ["o/r"], ["o/r", "7", "extra"]):
            with self.subTest(argv=argv):
                done = subprocess.run([sys.executable, "-I", str(LANDING / "codex_gate.py"), *argv], capture_output=True, text=True, timeout=30)
                self.assertEqual(done.returncode, 1)
                self.assertIn("usage: codex_gate.py <owner/repo> <pr>", done.stderr)


# ---------------------------------------------------------------------------------------------- 7. the scripts end to end
class EndToEndTests(LandingCase):
    """Each script runs whole against a scratch repository and a fake gh, python3 and sleep (no network, nothing merged)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        git(cls.dir, "init", "-q", "--bare", "-b", "main", "origin.git")
        cls.repo = cls.dir / "work"
        git(cls.dir, "init", "-q", "-b", "main", "work")
        git(cls.repo, "remote", "add", "origin", str(cls.dir / "origin.git"))
        (cls.repo / "base.txt").write_text("base\n")
        git(cls.repo, "add", "--", "base.txt")
        git(cls.repo, "commit", "-q", "-m", "base")
        cls.base = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "push", "-q", "origin", "main")
        git(cls.repo, "checkout", "-q", "-b", "pr")
        (cls.repo / "change.txt").write_text("change\n")
        git(cls.repo, "add", "--", "change.txt")
        git(cls.repo, "commit", "-q", "-m", "the change")
        cls.head = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "push", "-q", "origin", f"pr:refs/pull/{PR}/head")
        git(cls.repo, "checkout", "-q", "-b", "other", "main")
        (cls.repo / "other.txt").write_text("another change\n")
        git(cls.repo, "add", "--", "other.txt")
        git(cls.repo, "commit", "-q", "-m", "another change")
        cls.other = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "checkout", "-q", "main")
        (cls.repo / "moved.txt").write_text("main moved\n")  # main moves; the PR is then rebased onto it
        git(cls.repo, "add", "--", "moved.txt")
        git(cls.repo, "commit", "-q", "-m", "main moves")
        git(cls.repo, "push", "-q", "origin", "main")
        git(cls.repo, "checkout", "-q", "-b", "rebased", "main")
        git(cls.repo, "cherry-pick", cls.head)
        cls.rebased = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "checkout", "-q", "--detach", cls.base)  # the clone's HEAD is not the current main: the scripts must not use it
        cls.home = cls.dir / "home"
        cls.home.mkdir()

    def land(self, script, *, args=None, via=None, head=None, merge_state="CLEAN", rollup=None, checkruns=None, statuses=None,
             verdict=None, draft=False, **extra):
        """Run a landing; returns (exit code, stdout+stderr, the fake commands' log lines)."""
        run = self.dir / f"run-{next(self.counter)}"
        run.mkdir()
        gate = [check_run("ci-gate")] if rollup is None else rollup
        (run / "prview.json").write_text(json.dumps({
            "headRefOid": head or self.head, "isDraft": draft, "mergeStateStatus": merge_state, "statusCheckRollup": gate,
            "state": "MERGED", "mergeCommit": {"oid": "f" * 40}, "mergedAt": "2026-10-10T00:00:00Z"}))
        (run / "statuses.json").write_text(json.dumps(statuses or []))
        (run / "checkruns.json").write_text(json.dumps({"check_runs": checkruns if checkruns is not None else [nas_run("validate", "2026-10-10T10:00:00Z")]}))
        verdict_file = run / "verdict.md"
        verdict_file.write_text(verdict if verdict is not None else f"# Read\n\nVerdict: PASS at {self.head[:8]}\n", encoding="utf-8")
        environment = self.env(HOME=str(self.home), FAKE_LOG=str(run / "log"), FAKE_PRVIEW=str(run / "prview.json"),
                               FAKE_STATUSES=str(run / "statuses.json"), FAKE_CHECKRUNS=str(run / "checkruns.json"),
                               LANDING_UET_REPO=str(self.repo), LANDING_NAS_REPO=str(self.repo),
                               LANDING_COORD=str(self.dir / "coord"), GIT_AUTHOR_NAME="landing-test",
                               GIT_AUTHOR_EMAIL="landing@example.invalid", GIT_COMMITTER_NAME="landing-test",
                               GIT_COMMITTER_EMAIL="landing@example.invalid", **extra)
        if args is None:
            args = [PR, self.head[:12]] + ([str(verdict_file)] if script.key == "nas" else [])
        done = subprocess.run([str(via or script.path), *args], capture_output=True, text=True, env=environment, cwd=self.dir, timeout=240)
        log = (run / "log").read_text(encoding="utf-8").splitlines() if (run / "log").exists() else []
        return done.returncode, (done.stdout + done.stderr).strip(), log

    def gate_calls(self, log):
        return [line for line in log if line.startswith("python3 -I ") and "validate.py" not in line]

    def merge_calls(self, log):
        return [line for line in log if line.startswith("gh pr merge")]

    def test_uet_lands_when_every_gate_passes_pinned_to_the_head(self):
        code, out, log = self.land(self.uet)
        self.assertEqual(code, 0, out)
        self.assertIn("same change", out)
        self.assertEqual(self.merge_calls(log), [f"gh pr merge {PR} -R {UET_REPO} --squash --match-head-commit {self.head}"])
        gate = f"{os.path.realpath(LANDING)}/codex_gate.py"
        self.assertEqual(self.gate_calls(log), [f"python3 -I {gate} {UET_REPO} {PR}"] * 2, "before the wait and before the merge")

    def test_nas_lands_when_every_gate_passes_after_validating_the_merge(self):
        code, out, log = self.land(self.nas)
        self.assertEqual(code, 0, out)
        self.assertIn("the merge onto current main validates", out)
        self.assertEqual(self.merge_calls(log), [f"gh pr merge {PR} -R {NAS_REPO} --squash --match-head-commit {self.head}"])
        gate = f"{os.path.realpath(LANDING)}/codex_gate.py"
        self.assertEqual(self.gate_calls(log), [f"python3 -I {gate} {NAS_REPO} {PR}"] * 2)
        self.assertEqual([line for line in log if "validate.py" in line], ["python3 -E -s -B scripts/validate.py"])
        trees = [line for line in log if line.startswith("validate-tree ")]
        self.assertEqual(len(trees), 1)
        # the head's change (change.txt) merged onto the CURRENT main (moved.txt), not onto the clone's HEAD
        self.assertEqual(sorted(trees[0].split()[1:]), ["base.txt", "change.txt", "moved.txt"])
        self.assertEqual(sorted(Path("/var/tmp").glob(f"nas-land-{PR}-*")), [], "the temporary worktree is removed")

    def test_gate_path_follows_the_real_script_through_a_symlink_and_a_wrapper(self):
        for script in (self.uet, self.nas):
            link_dir = self.dir / f"link-{next(self.counter)}"
            link_dir.mkdir()
            link = link_dir / f"{script.key}-land"
            link.symlink_to(script.path)
            wrapper = link_dir / f"{script.key}-wrapper"
            wrapper.write_text(f'#!/bin/sh\nexec {q(script.path)} "$@"\n', encoding="utf-8")
            wrapper.chmod(0o755)
            expected = f"{os.path.realpath(LANDING)}/codex_gate.py"
            for name, via, extra, gate in (("symlink", link, {}, expected), ("wrapper", wrapper, {}, expected),
                                           ("LANDING_GATE", link, {"LANDING_GATE": "/elsewhere/gate.py"}, "/elsewhere/gate.py")):
                with self.subTest(script=script.key, via=name):
                    code, out, log = self.land(script, via=via, **extra)
                    self.assertEqual(code, 0, out)
                    repo = UET_REPO if script.key == "uet" else NAS_REPO
                    self.assertEqual(self.gate_calls(log), [f"python3 -I {gate} {repo} {PR}"] * 2)

    def test_arguments_and_the_read_head_are_checked_first(self):
        code, out, log = self.land(self.nas, args=[PR, self.head[:12]])
        self.assertEqual((code, "no verdict file given" in out), (2, True), out)
        for script, text in ((self.uet, "not resolvable"), (self.nas, "not resolvable")):
            with self.subTest(script=script.key):
                args = [PR, "deadbeefdeadbeef"] + ([str(self.dir / "v.md")] if script.key == "nas" else [])
                code, out, log = self.land(script, args=args)
                self.assertEqual((code, text in out), (3, True), out)
                self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))

    def test_a_success_status_is_checked_against_its_record_under_landing_coord(self):
        record_dir = self.dir / "coord/trading-cc/reads"
        record_dir.mkdir(parents=True, exist_ok=True)
        name = f"landing-{next(self.counter)}.md"
        status = [{"context": "trading-cc-read", "state": "success", "description": f"PASS: trading-cc/reads/{name}",
                   "updated_at": "2026-10-10T00:00:00Z"}]
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, record="missing"):
                code, out, log = self.land(script, statuses=status)
                self.assertEqual((code, "record missing" in out), (2, True), out)
        (record_dir / name).write_text(f"# r\n\nVerdict: CHANGES_REQUESTED at {self.head[:8]}\n", encoding="utf-8")
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, record="changes requested"):
                code, out, log = self.land(script, statuses=status)
                self.assertEqual((code, self.merge_calls(log)), (2, []), out)
        (record_dir / name).write_text(f"# r\n\nVerdict: CHANGES_REQUESTED at {self.head[:8]}\n\nVerdict: PASS at {self.head[:8]}\n", encoding="utf-8")
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, record="pass"):
                code, out, log = self.land(script, statuses=status)
                self.assertEqual(code, 0, out)
                self.assertIn("record verified", out)

    def test_verdict_gate_stops_before_codex_and_before_any_merge(self):
        refused = f"# Read\n\nVerdict: CHANGES_REQUESTED at {self.head[:8]}\n"
        code, out, log = self.land(self.nas, verdict=refused)
        self.assertEqual(code, 2, out)
        self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))
        uet_file = self.dir / f"uet-verdict-{next(self.counter)}.md"
        uet_file.write_text(refused, encoding="utf-8")
        code, out, log = self.land(self.uet, VERDICT_FILES=str(uet_file))
        self.assertEqual(code, 2, out)
        self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))

    def test_a_failing_trading_cc_read_status_stops_both_scripts(self):
        status = [{"context": "trading-cc-read", "state": "failure", "description": "CHANGES_REQUESTED: trading-cc/reads/x.md",
                   "updated_at": "2026-10-10T00:00:00Z"}]
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, statuses=status)
                self.assertEqual(code, 2, out)
                self.assertIn("trading-cc-read is failure", out)
                self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))

    def test_a_pure_rebase_of_the_read_head_lands_pinned_to_the_new_head(self):
        for script, repo in ((self.uet, UET_REPO), (self.nas, NAS_REPO)):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, head=self.rebased)
                self.assertEqual(code, 0, out)
                self.assertNotEqual(self.rebased, self.head)
                self.assertEqual(self.merge_calls(log), [f"gh pr merge {PR} -R {repo} --squash --match-head-commit {self.rebased}"])

    def test_a_draft_is_marked_ready_before_codex_is_asked(self):
        for script, repo in ((self.uet, UET_REPO), (self.nas, NAS_REPO)):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, draft=True)
                self.assertEqual(code, 0, out)
                self.assertIn("marked ready", out)
                ready = log.index(f"gh pr ready {PR} -R {repo}")
                self.assertLess(ready, min(i for i, line in enumerate(log) if line.startswith("python3 -I ")))

    def test_the_head_moving_after_the_read_stops_the_landing(self):
        # headRefOid answers in sequence: the first read of the head, then the later ones
        code, out, log = self.land(self.uet, FAKE_HEADS=f"{self.head} {self.other}")
        self.assertEqual(code, 4, out)
        self.assertIn("CHANGE DIFFERS", out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.uet, FAKE_HEADS=f"{self.head} {self.head} {self.other}")
        self.assertEqual(code, 3, out)
        self.assertIn("head moved to", out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.nas, FAKE_HEADS=f"{self.head} {self.other}")
        self.assertEqual(code, 3, out)
        self.assertIn("head moved to", out)
        self.assertEqual(self.merge_calls(log), [])

    def test_codex_reopening_between_the_wait_and_the_merge_stops_with_9(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, FAKE_GATE_SEQ="0 3", FAKE_GATE_LINE="Codex review running since 2026-10-10T00:00:00Z")
                self.assertEqual(code, 9, out)
                self.assertIn("just before the merge", out)
                self.assertEqual((len(self.gate_calls(log)), self.merge_calls(log)), (2, []))

    def test_codex_gate_codes_map_to_continue_poll_or_stop(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, gate="running forever (3)"):
                code, out, log = self.land(script, FAKE_GATE_RC="3", FAKE_GATE_LINE="Codex review running since 2026-10-10T00:00:00Z")
                self.assertEqual(code, 9, out)
                self.assertEqual((len(self.gate_calls(log)), self.merge_calls(log)), (21, []))
            with self.subTest(script=script.key, gate="ended other than Completed (4)"):
                code, out, log = self.land(script, FAKE_GATE_RC="4", FAKE_GATE_LINE="Codex review ended 'Cancelled' at 2026-10-10T00:00:00Z; not Completed")
                self.assertEqual(code, 9, out)
                self.assertEqual((len(self.gate_calls(log)), self.merge_calls(log)), (1, []))

    def test_codex_unavailable_needs_the_gpt_verdict_in_uet_and_proceeds_in_nas(self):
        unavailable = {"FAKE_GATE_RC": "5", "FAKE_GATE_LINE": "Codex unavailable: usage-limit or account notice"}
        code, out, log = self.land(self.uet, **unavailable)
        self.assertEqual(code, 9, out)
        self.assertIn("Codex unavailable: set GPT_VERDICT", out)
        self.assertEqual(self.merge_calls(log), [])
        accepted = self.dir / f"gpt-{next(self.counter)}.md"
        accepted.write_text(f"# GPT verdict on PR x#1 at {self.head}: ACK\n", encoding="utf-8")
        code, out, log = self.land(self.uet, GPT_VERDICT=str(accepted), **unavailable)
        self.assertEqual(code, 0, out)
        self.assertIn("substitute GPT verdict", out)
        self.assertEqual(len(self.merge_calls(log)), 1)
        refused = self.dir / f"gpt-{next(self.counter)}.md"
        refused.write_text(f"# GPT verdict on PR x#1 at {self.head}: CHANGES_REQUESTED\n\nACK elsewhere\n", encoding="utf-8")
        code, out, log = self.land(self.uet, GPT_VERDICT=str(refused), **unavailable)
        self.assertEqual(code, 9, out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.nas, **unavailable)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.merge_calls(log)), 1)

    def test_head_that_is_not_the_read_head_nor_its_rebase_stops_with_3(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, head=self.other)
                self.assertEqual(code, 3, out)
                self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))

    def test_ci_failing_incomplete_and_blocked_stop_before_the_merge(self):
        failing = [check_run("ci-gate"), check_run("bad", "COMPLETED", "FAILURE")]
        running = [check_run("ci-gate"), check_run("slow", "IN_PROGRESS", "")]
        code, out, log = self.land(self.uet, rollup=failing)
        self.assertEqual(code, 5, out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.uet, rollup=running)
        self.assertEqual((code, "CI timeout" in out, self.merge_calls(log)), (6, True, []), out)
        code, out, log = self.land(self.uet, merge_state="BLOCKED", FAKE_OPEN_THREADS="3")
        self.assertEqual(code, 8, out)
        self.assertIn("unresolved review threads: 3", out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.nas, checkruns=[nas_run("validate", "2026-10-10T10:00:00Z", conclusion="failure")])
        self.assertEqual(code, 5, out)
        code, out, log = self.land(self.nas, merge_state="BLOCKED")
        self.assertEqual(code, 8, out)
        self.assertEqual(self.merge_calls(log), [])

    def test_nas_stops_with_10_when_the_merge_with_current_main_fails_validation(self):
        code, out, log = self.land(self.nas, FAKE_VALIDATE_RC="1")
        self.assertEqual(code, 10, out)
        self.assertIn("validate.py on the merge with current main exited 1", out)
        self.assertEqual(self.merge_calls(log), [])
        self.assertEqual(sorted(Path("/var/tmp").glob(f"nas-land-{PR}-*")), [])

    def test_a_failed_merge_call_is_exit_7_and_a_behind_branch_is_updated_first(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, case="merge refused"):
                code, out, log = self.land(script, FAKE_MERGE_RC="1")
                self.assertEqual(code, 7, out)
        code, out, log = self.land(self.nas, merge_state="BEHIND")
        self.assertEqual(code, 0, out)
        self.assertIn("same change", out)
        self.assertTrue(any(line.startswith(f"gh pr update-branch {PR} -R {NAS_REPO}") for line in log))
        code, out, log = self.land(self.nas, merge_state="BEHIND", FAKE_UPDATE_RC="1")
        self.assertEqual(code, 4, out)  # a code the script's header does not list
        self.assertIn("update-branch refused", out)
        self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))


if __name__ == "__main__":
    unittest.main()
